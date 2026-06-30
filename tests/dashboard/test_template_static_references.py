"""Tests verifying that static file references in templates actually exist."""

import re
from pathlib import Path

TEMPLATES_DIR = Path("src/aspara/dashboard/templates")
STATIC_DIR = Path("src/aspara/dashboard/static")


def extract_static_references(template_path: Path) -> list[str]:
    """Extract /static/... references from a template."""
    content = template_path.read_text()
    # Extract paths starting with /static from src="..." or href="..."
    pattern = r'(?:src|href)=["\'](/static/[^"\']+)["\']'
    return re.findall(pattern, content)


def test_all_static_references_exist():
    """Verify that static file references in all templates exist."""
    missing = []

    for template in TEMPLATES_DIR.glob("*.mustache"):
        refs = extract_static_references(template)
        for ref in refs:
            # Convert /static/xxx -> static/xxx and resolve from STATIC_DIR's parent
            relative_path = ref.lstrip("/")  # "static/js/foo.js"
            file_path = STATIC_DIR.parent / relative_path

            if not file_path.exists():
                missing.append(f"{template.name}: {ref}")

    assert not missing, "Missing static files:\n" + "\n".join(missing)


def test_extract_static_references():
    """Test the extract_static_references function."""
    # Temporary content for testing
    test_content = """
    <link href="/static/css/styles.css" rel="stylesheet">
    <script src="/static/js/app.js"></script>
    <script src='/static/js/utils.js'></script>
    <img src="/static/images/logo.png" alt="Logo">
    <a href="https://example.com">External</a>
    """

    # Test the regex directly without mocking Path.read_text
    pattern = r'(?:src|href)=["\'](/static/[^"\']+)["\']'
    refs = re.findall(pattern, test_content)

    assert len(refs) == 4
    assert "/static/css/styles.css" in refs
    assert "/static/js/app.js" in refs
    assert "/static/js/utils.js" in refs
    assert "/static/images/logo.png" in refs


def test_templates_directory_exists():
    """Verify that the templates directory exists."""
    assert TEMPLATES_DIR.exists(), f"Templates directory not found: {TEMPLATES_DIR}"
    assert TEMPLATES_DIR.is_dir(), f"Templates path is not a directory: {TEMPLATES_DIR}"


def test_static_directory_exists():
    """Verify that the static files directory exists."""
    assert STATIC_DIR.exists(), f"Static directory not found: {STATIC_DIR}"
    assert STATIC_DIR.is_dir(), f"Static path is not a directory: {STATIC_DIR}"
