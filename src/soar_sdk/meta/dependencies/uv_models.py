from pydantic import BaseModel


class UvDependency(BaseModel):
    """Represents a Python dependency relationship loaded from the uv lock."""

    name: str


class UvSource(BaseModel):
    """Represents the source of a Python package in the uv lock."""

    registry: str | None = None
    directory: str | None = None
