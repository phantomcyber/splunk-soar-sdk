# View Handlers

View handlers are functions that process action results and prepare data for template rendering. They bridge the gap between your action's output and the HTML display by transforming raw results into data to be injected into your template.

## Basic Handler Structure

A view handler is a regular Python function decorated with `@app.view_handler`:

```python
@app.view_handler(template="my_template.html")
def my_view_handler(output: list[MyActionOutput]) -> dict:
    # Process the action results
    # Return data for template rendering
    return {
        "key": "value",
        "data": processed_data
    }
```

## Handler Parameters

### Input: Action Results
View handlers receive the action's output as their first parameter. The type should match your action's return type:

```python
def handler(output: list[MyActionOutput]) -> dict:
    return {"results": [r.some_field for r in output]}
```

### Return: Template Data
Handlers must return a dictionary containing data for template rendering. Keys become variables accessible in your Jinja2 template:

```python
def handler(output: list[DetectionOutput]) -> dict:
    return {
        "title": "Detection Results",
        "total_detections": len(output),
        "detections": [
            {
                "id": d.detection_id,
                "message": d.message,
                "severity": d.severity
            }
            for d in output
        ]
    }
```

## Decorator Options

### Using Templates
Specify a custom HTML template file:

```python
# Template file: templates/detection_results.html
@app.view_handler(template="detection_results.html")
def render_detections(output: list[DetectionOutput]) -> dict:
    return {"detections": output}
```

### Using Components
Use pre-built reusable components:
- Return output data will define the reusable component used

```python
@app.view_handler()
def render_as_table(output: list[DetectionOutput]) -> TableData:
    return TableData(
        title="Detection Results",
        headers=["ID", "Message", "Severity"],
        rows=[[d.detection_id, d.message, d.severity] for d in output]
    )
```

## Attaching to Actions

Connect your view handler to an action using the `view_handler` parameter:

```python
@app.action(
    name="scan file",
    view_handler=render_detections
)
def scan_file_action(params: ScanParams, client: SOARClient) -> list[DetectionOutput]:
    # Your action implementation
    return detection_results
```
