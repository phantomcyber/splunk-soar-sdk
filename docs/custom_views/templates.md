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

## SDK Template Features

### Widget Template Structure
When making a new template to get full usage, SOAR styling and configuration blocks. This preamble tells the SOAR platform how to style your widget.

**Example Preamble:**
```html
{% extends 'widgets/widget_template.html' %}

{% block title_color %}{{ title_color or '#28a745' }}{% endblock %}
{% block title_text_color %}{{ title_text_color or 'white' }}{% endblock %}
{% block body_color %}{{ body_color or 'white' }}{% endblock %}
{% block body_text_color %}{{ body_text_color or '#8775a7' }}{% endblock %}

<!-- Add app icon as title -->
{% block custom_title_prop %}{% if title_logo %}style="background-size: auto 60%; background-position: 50%; background-repeat: no-repeat; background-image: url('/app_resource/{{ title_logo }}');"{% endif %}{% endblock %}

{% block custom_tools %}
  {% include 'widgets/widget_resize_snippet.html' %}
{% endblock %}

{% block widget_content %}
<!-- Content goes here -->
{% endblock %}
```

**Example:**
```html
<!-- templates/user_summary.html -->
{% extends 'widgets/widget_template.html' %}

{% block title_color %}{{ title_color or '#007bff' }}{% endblock %}
{% block title_text_color %}{{ title_text_color or 'white' }}{% endblock %}
{% block body_color %}{{ body_color or 'white' }}{% endblock %}
{% block body_text_color %}{{ body_text_color or '#333' }}{% endblock %}

{% block title1 %}User Summary{% endblock %}
{% block title2 %}{{ user.name }}{% endblock %}

{% block custom_tools %}
  {% include 'widgets/widget_resize_snippet.html' %}
{% endblock %}

{% block widget_content %}
<div style="display: flex;">
  <div style="flex: 1;">
    <h3>Account Details</h3>
    <p><strong>Email:</strong> {{ user.email }}</p>
    <p><strong>Role:</strong> {{ user.role }}</p>
    <p><strong>Status:</strong>
      <span style="color: {{ user.status == 'active' and '#28a745' or '#dc3545' }}">
        {{ user.status|title }}
      </span>
    </p>
  </div>
  <div style="flex: 1;">
    <h3>Statistics</h3>
    <p><strong>Last Login:</strong> {{ user.last_login|human_datetime }}</p>
    <p><strong>Total Logins:</strong> {{ user.login_count|safe_intcomma }}</p>
  </div>
</div>
{% endblock %}
```

### Auto-escaping and Security
Templates automatically escape HTML to prevent XSS attacks. The SDK enables:
- `autoescape=True` for all HTML templates
- `trim_blocks=True` and `lstrip_blocks=True` for cleaner output

**Use `|safe` for:**
- JSON data: like `{{ data|to_json|safe }}`
- Pre-sanitized HTML: like `{{ content|bleach|safe }}`
