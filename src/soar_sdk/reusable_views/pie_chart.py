from typing import Any
from pydantic import BaseModel


class PieChartData(BaseModel):
    """Data model for pie chart reusable component."""

    title: str
    labels: list[str]
    values: list[int]
    colors: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert the PieChartData instance to a dictionary for template."""
        return {
            "title": self.title,
            "labels": self.labels,
            "values": self.values,
            "colors": self.colors,
        }
