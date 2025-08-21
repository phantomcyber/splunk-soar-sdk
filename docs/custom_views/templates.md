# Templates

Templates are Jinja2 HTML files that define how your action results are displayed. They receive data from view handlers and render it into the final HTML that users see in the SOAR interface.

For Jinja2 syntax and features, see the [official Jinja2 documentation](https://jinja.palletsprojects.com/en/stable/).

## Template Location

Store your templates in the `templates/` directory of your app:

```
my_app/
├── src/
│   └── app.py
├── templates/
│   ├── detection_results.html
│   ├── user_summary.html
│   └── scan_report.html
└── pyproject.toml
```

### SDK-Specific Filters
The SOAR SDK provides custom filters for common needs:

```html
<!-- Human-readable formatting -->
<p>Modified: {{ last_modified|human_datetime }}</p>
<p>Count: {{ total_items|safe_intcomma }}</p>

<!-- JSON data for JavaScript -->
<script>
const data = {{ json_data|to_json|safe }};
</script>

<!-- More filters available... -->
```

**Important:** Use `|safe` when outputting JSON data or pre-sanitized HTML. Normal text and variables are automatically escaped.

## Widget Templates

All custom views in SOAR use the widget template system, providing consistent styling and functionality.

**Note:** You can also create fully custom templates without extending any base should it be desired.

### Base Template Options

Choose a base header. The base headers sets up base template defining widget structure, styling, standard functionality like resizing.

#### `base/logo_header.html`
Use when you want your app's logo in the widget header (most common).

```html
{% extends 'base/logo_header.html' %}

{% block widget_content %}
<div>
  <h3>Results</h3>
  <p>{{ my_data }}</p>
</div>
{% endblock %}
```

#### `base/header.html`
Standard header with text-based titles.

```html
{% extends 'base/header.html' %}

{% block title %}My Custom Title{% endblock %}
{% block subtitle %}Secondary Text{% endblock %}

{% block widget_content %}
<div>
  <h3>Results</h3>
  <p>{{ my_data }}</p>
</div>
{% endblock %}
```

### Override Base Template Blocks

These are base template blocks can be overridden when creating a template:

#### Content Blocks
- `widget_content` - Main content area (required)
- `title` - Primary title text
- `subtitle` - Secondary title text

#### Styling Blocks
- `title_text_color` - CSS color for title text
- `extra_classes` - Additional CSS classes for the widget container
- `update_type` - Widget update behavior

#### Other Blocks
- `custom_title_prop` - Custom properties for the title element

### Theming
Widgets automatically conform to SOAR's light and dark themes. Background colors, text colors, and logo variants are handled based on theme unless overridden.

### Example Template

```html
<!-- templates/service_status.html -->
{% extends 'base/logo_header.html' %}

{% block widget_content %}
<h3>Service Status</h3>
{% for service in services %}
<div style="margin-bottom: 1rem;">
  <h4>{{ service.name }}</h4>
  <p><strong>Status:</strong> {{ service.status }}</p>
  <p><strong>Uptime:</strong> {{ service.uptime }}</p>
</div>
{% endfor %}
{% endblock %}
```

### Auto-escaping and Security
Templates automatically escape HTML to prevent XSS attacks. The SDK enables:
- `autoescape=True` for all HTML templates
- `trim_blocks=True` and `lstrip_blocks=True` for cleaner output

**Use `|safe` for:**
- JSON data: like `{{ data|to_json|safe }}`
- Pre-sanitized HTML: like `{{ content|bleach|safe }}`
