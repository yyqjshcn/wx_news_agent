"""
Load prompts and templates from external files.
Priority: {name}.json > {name}.template.json (same for .html templates)
"""
import json
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_prompt(name: str) -> dict:
    """Load prompt JSON file. Tries {name}.json first, falls back to {name}.template.json."""
    custom_path = PROMPTS_DIR / f"{name}.json"
    template_path = PROMPTS_DIR / f"{name}.template.json"

    path = custom_path if custom_path.exists() else template_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {name} (looked in {PROMPTS_DIR})")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_template(name: str) -> Template:
    """Load HTML template. Tries {name}.html first, falls back to {name}.template.html."""
    custom_path = TEMPLATES_DIR / f"{name}.html"
    template_path = TEMPLATES_DIR / f"{name}.template.html"

    path = custom_path if custom_path.exists() else template_path
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {name} (looked in {TEMPLATES_DIR})")

    with open(path, encoding="utf-8") as f:
        return Template(f.read())
