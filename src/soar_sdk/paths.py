from pathlib import Path

SDK_ROOT = Path(__file__).parent

# View templates (built into the SDK)
SDK_TEMPLATES = SDK_ROOT / "templates"

# App's templates
APP_TEMPLATES = Path("templates")

# App's documentation files
APP_README = Path("README.md")
APP_LICENSE = Path("LICENSE")
APP_NOTICE = Path("NOTICE")
APP_RELEASE_NOTES = Path("release_notes")

APP_INIT_TEMPLATES = SDK_ROOT / "app_templates"
