from enum import Enum
from pydantic import BaseModel

from .pie_chart import PieChartData


# Add in component types as implemented
class ComponentType(Enum):
    PIE_CHART = "pie_chart"

    @property
    def data_model(self) -> type[BaseModel]:
        """Get the data model class for this component type for validation."""
        return _COMPONENT_DATA_MODELS[self]


_COMPONENT_DATA_MODELS = {
    ComponentType.PIE_CHART: PieChartData,
}

__all__ = ["ComponentType", "PieChartData"]
