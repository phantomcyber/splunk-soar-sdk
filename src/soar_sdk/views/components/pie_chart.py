from pydantic import BaseModel


class PieChartData(BaseModel):
    """Data model for pie chart reusable component."""

    title: str
    labels: list[str]
    values: list[int]
    colors: list[str]
