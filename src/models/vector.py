"""Lightweight PostgreSQL pgvector SQLAlchemy type."""

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """Represent a pgvector VECTOR(n) column without optional dependency."""

    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:  # type: ignore[no-untyped-def]
        return f"VECTOR({self.dimensions})"
