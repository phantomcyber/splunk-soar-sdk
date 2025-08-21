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

Each component is linked through its corresponding data model. Just return the appropriate component data model with its content to render the component.

### Pie Chart Component

Display data as a pie chart with customizable colors and labels.

```python
from soar_sdk.views.components.pie_chart import PieChartData

@app.view_handler()
def render_threat_distribution(output: list[ThreatAnalysisOutput]) -> PieChartData:
    output = output[0]

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
