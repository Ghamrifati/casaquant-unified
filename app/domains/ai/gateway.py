"""CasaQuant Unified — AI Gateway with circuit breaker, retry, and healthcheck.

Isolates Ollama fragility from business logic.
"""

import hashlib
import json
import logging
import threading
import time
from enum import Enum

import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("casaquant.ai.gateway")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AIGatewayConfig(BaseModel):
    host: str = settings.ollama_host
    timeout: int = settings.ollama_timeout
    max_retries: int = settings.ollama_max_retries
    backoff: int = settings.ollama_backoff
    max_connections: int = 10
    max_keepalive: int = 5


class AIGateway:
    """Resilient gateway to Ollama LLM server.

    Features:
    - Persistent HTTP client with connection pooling
    - Automatic client recreation if connection dies
    - Retry with exponential backoff
    - Circuit breaker (CLOSED / OPEN / HALF_OPEN)
    - Healthcheck before each request
    - Configurable num_predict / num_ctx per mode
    """

    # Mode-specific token budgets (from DIAGNOSTIC_OLLAMA)
    MODE_TOKENS = {
        "iq_score": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "signaux": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "bpf": {"num_predict": 1024, "num_ctx": 8192, "temperature": 0.7},
        "risque": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "alpha": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "chart": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "rsi_timing": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "recommandation": {"num_predict": 1024, "num_ctx": 8192, "temperature": 0.7},
        "entree": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "sortie": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.7},
        "risques_complet": {"num_predict": 1024, "num_ctx": 8192, "temperature": 0.7},
        "predictif": {"num_predict": 1024, "num_ctx": 8192, "temperature": 0.7},
        "portfolio": {"num_predict": 1536, "num_ctx": 8192, "temperature": 0.7},
        "chat": {"num_predict": 800, "num_ctx": 8192, "temperature": 0.8},
    }

    def __init__(self, config: AIGatewayConfig | None = None):
        self.cfg = config or AIGatewayConfig()
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()

        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._failure_threshold = 3
        self._recovery_timeout = 30  # seconds
        self._last_failure_time: float | None = None

    def _get_client(self) -> httpx.Client:
        """Return a healthy httpx client, recreating if needed."""
        with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.Client(
                    base_url=self.cfg.host,
                    timeout=httpx.Timeout(
                        connect=10,
                        read=self.cfg.timeout,
                        write=10,
                        pool=10,
                    ),
                    limits=httpx.Limits(
                        max_connections=self.cfg.max_connections,
                        max_keepalive_connections=self.cfg.max_keepalive,
                    ),
                )
                logger.info("AIGateway: recreated httpx client for %s", self.cfg.host)
            return self._client

    def _healthcheck(self) -> bool:
        """Quick healthcheck to Ollama."""
        try:
            resp = self._get_client().get("/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("AIGateway healthcheck failed: %s", exc)
            return False

    def _circuit_ok(self) -> bool:
        """Check if circuit breaker allows a request."""
        if self._circuit_state == CircuitState.CLOSED:
            return True
        if self._circuit_state == CircuitState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) > self._recovery_timeout:
                logger.info("AIGateway: circuit entering HALF_OPEN")
                self._circuit_state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN — allow one probe
        return True

    def _record_success(self):
        """Reset circuit breaker on success."""
        if self._circuit_state == CircuitState.HALF_OPEN:
            logger.info("AIGateway: circuit CLOSED (recovery successful)")
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _record_failure(self):
        """Record a failure, potentially opening the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            logger.warning("AIGateway: circuit OPEN (threshold reached)")
            self._circuit_state = CircuitState.OPEN

    def generate(
        self,
        prompt: str,
        model: str = settings.ollama_model,
        mode: str = "chat",
        system_prompt: str = "",
        stream: bool = True,
    ):
        """Generate text from Ollama with resilience.

        Yields dict chunks {token: str, done: bool} or raises on failure.
        """
        if not self._circuit_ok():
            raise RuntimeError("Circuit breaker OPEN — Ollama indisponible")

        # Merge system prompt
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        token_cfg = self.MODE_TOKENS.get(mode, self.MODE_TOKENS["chat"])
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": stream,
            "keep_alive": "30m",
            "options": {
                "temperature": token_cfg["temperature"],
                "num_predict": token_cfg["num_predict"],
                "num_ctx": token_cfg["num_ctx"],
            },
        }

        last_exception: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                client = self._get_client()
                if stream:
                    with client.stream(
                        "POST", "/api/generate", json=payload, timeout=self.cfg.timeout + 10
                    ) as response:
                        response.raise_for_status()
                        saw_done = False
                        for line in response.iter_lines():
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                if data.get("response"):
                                    yield {"token": data["response"], "done": False}
                                if data.get("done"):
                                    saw_done = True
                                    yield {"token": "", "done": True}
                                    break
                            except json.JSONDecodeError:
                                continue
                        # Fallback done signal if stream ends without explicit done
                        if not saw_done:
                            yield {"token": "", "done": True, "fallback": True}
                else:
                    resp = client.post("/api/generate", json=payload, timeout=self.cfg.timeout + 10)
                    resp.raise_for_status()
                    data = resp.json()
                    yield {"token": data.get("response", ""), "done": True}

                self._record_success()
                return

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                logger.warning(
                    "AIGateway attempt %d/%d failed for mode=%s: %s",
                    attempt + 1,
                    self.cfg.max_retries + 1,
                    mode,
                    exc,
                )
                self._record_failure()
                if attempt < self.cfg.max_retries:
                    backoff = self.cfg.backoff * (2 ** attempt)
                    logger.info("AIGateway retrying in %d seconds...", backoff)
                    time.sleep(backoff)
                else:
                    break
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                logger.error("AIGateway HTTP error %s: %s", exc.response.status_code, exc)
                self._record_failure()
                break
            except Exception as exc:
                last_exception = exc
                logger.exception("AIGateway unexpected error")
                self._record_failure()
                break

        raise RuntimeError(f"AIGateway failed after {self.cfg.max_retries + 1} attempts: {last_exception}")

    @staticmethod
    def compute_prompt_hash(prompt: str, system_prompt: str = "", model: str = settings.ollama_model) -> str:
        """Compute a stable hash for cache keys."""
        content = f"{model}::{system_prompt}::{prompt}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


# Global singleton gateway instance
ai_gateway = AIGateway()
