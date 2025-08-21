from pathlib import Path

SDK_ROOT = Path(__file__).parent

# View templates (built into the SDK)
SDK_TEMPLATES = SDK_ROOT / "templates"

# App's templates
APP_TEMPLATES = Path("templates")

APP_INIT_TEMPLATES = SDK_ROOT / "app_templates"
