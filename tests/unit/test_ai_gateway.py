"""Tests for AI Gateway circuit breaker and retry logic."""

import pytest

from app.domains.ai.gateway import AIGateway, CircuitState


class TestAIGateway:
    def test_circuit_starts_closed(self):
        gw = AIGateway()
        assert gw._circuit_state == CircuitState.CLOSED

    def test_record_failure_increments(self):
        gw = AIGateway()
        gw._record_failure()
        assert gw._failure_count == 1
        assert gw._circuit_state == CircuitState.CLOSED  # below threshold

    def test_circuit_opens_after_threshold(self):
        gw = AIGateway()
        gw._failure_threshold = 2
        gw._record_failure()
        gw._record_failure()
        assert gw._circuit_state == CircuitState.OPEN

    def test_record_success_resets(self):
        gw = AIGateway()
        gw._failure_count = 2
        gw._circuit_state = CircuitState.HALF_OPEN
        gw._record_success()
        assert gw._failure_count == 0
        assert gw._circuit_state == CircuitState.CLOSED

    def test_circuit_ok_when_closed(self):
        gw = AIGateway()
        assert gw._circuit_ok() is True

    def test_circuit_not_ok_when_open(self):
        gw = AIGateway()
        gw._circuit_state = CircuitState.OPEN
        gw._last_failure_time = 9999999999  # far future
        assert gw._circuit_ok() is False

    def test_compute_prompt_hash(self):
        h1 = AIGateway.compute_prompt_hash("test prompt")
        h2 = AIGateway.compute_prompt_hash("test prompt")
        h3 = AIGateway.compute_prompt_hash("different prompt")
        assert h1 == h2
        assert h1 != h3
