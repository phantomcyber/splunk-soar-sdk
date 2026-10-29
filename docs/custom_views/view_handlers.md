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

### Optional Parameters and Summaries

Declare keyword-only `params` and `summary` arguments to receive the saved action
parameters and action-result summaries alongside the outputs:

```python
@app.view_handler(template="query_results.html")
def render_queries(
    outputs: list[QueryOutput],
    *,
    params: list[QueryParams],
    summary: list[QuerySummary],
) -> dict:
    return {
        "rows": [
            {"event": event, "query": param.query, "sid": item_summary.sid}
            for event, param, item_summary in zip(outputs, params, summary, strict=True)
        ]
    }
```

`QueryParams` is the action's `Params` subclass and `QuerySummary` is its
`ActionOutput` summary model. The SDK validates the saved metadata using the
argument annotations. Use `list[dict]`, or omit the annotation on the magic
argument, to receive dictionaries instead.

Both arguments are optional and independent. Each requested list has the same
length and ordering as `outputs`: `params[i]` and `summary[i]` belong to
`outputs[i]`. For an action result containing three events, its parameters and
summary appear three times in their respective lists. This also preserves the
association when the view receives multiple action results or app runs, without
adding metadata fields to the event data.

Action results with no events contribute no entries to these lists. If there are
no events at all, the handler receives empty lists, so these arguments cannot
provide metadata for empty action results.

The existing positional handler forms remain supported: `(outputs)`,
`(context, outputs)`, and `(context, action, outputs)`. Add the magic arguments
after `*` to keep them separate from those positional arguments. Handlers that
omit them retain their existing behavior, and their metadata is not read.

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
def scan_file_action(params: ScanParams, soar: SOARClient) -> list[DetectionOutput]:
    # Your action implementation
    return detection_results
```
