"""CasaQuant Unified — Market domain models (SQLModel)."""

from typing import Optional

from sqlmodel import Field, SQLModel


class Ticker(SQLModel, table=True):
    """BVC ticker master data."""

    __tablename__ = "tickers"

    id: Optional[int] = Field(default=None, primary_key=True)
    code_bc: str = Field(max_length=20, unique=True)
    nom: str = Field(max_length=200)
    secteur: Optional[str] = Field(default=None, max_length=100)
    actif: bool = Field(default=True)
    illiquide: bool = Field(default=False)
