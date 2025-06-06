# Reusable Components

The SDK provides pre-built view components for common data visualization needs. These components handle the template rendering automatically, so you only need to structure your data according to their expected format.

> **Note:** Currently, only the Pie Chart component is available as an example. Additional and enriched components (Table, JSON, Chart, etc.) are planned for the future.

## How Components Work

Components are an alternative to custom templates that provide:
- **Pre-built visualization**: Ready-to-use charts and widgets
- **Automatic template handling**: No need to write HTML templates
- **Data validation**: Pydantic models ensure correct data structure
- **Interactive features**: Built-in hover effects and responsive design

Instead of returning a dictionary for template rendering, component view handlers return specific data model instances that the component knows how to render.

## Usage

Components are defined using the `ComponentType` enum, which ensures type safety and automatic validation. Reusable components should be easily discoverable via `ComponentType.(options)`.

Each component type is linked to a corresponding data model. The enum values and their associated data models are tightly coupled, preventing components from being used with incompatible data models.

### Pie Chart Component

Display data as a pie chart with customizable colors and labels.

```python
from soar_sdk.reusable_views import ComponentType, PieChartData

@app.view_handler(component=ComponentType.PIE_CHART)
def render_threat_distribution(output: ThreatAnalysisOutput) -> PieChartData:
    return PieChartData(
        title="Threat Distribution",
        labels=["Malware", "Phishing", "Suspicious", "Clean"],
        values=[output.malware_count, output.phishing_count, output.suspicious_count, output.clean_count],
        colors=["#dc3545", "#fd7e14", "#ffc107", "#28a745"]
    )
```

**PieChartData Parameters:**
- `title: str` - Chart title
- `labels: list[str]` - Labels for each data segment
- `values: list[int]` - Numeric values for each segment
- `colors: list[str]` - Custom colors for each segment
