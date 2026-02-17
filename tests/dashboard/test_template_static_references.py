"""テンプレート内の静的ファイル参照が実際に存在するか検証するテスト"""

import re
from pathlib import Path

TEMPLATES_DIR = Path("src/aspara/dashboard/templates")
STATIC_DIR = Path("src/aspara/dashboard/static")


def extract_static_references(template_path: Path) -> list[str]:
    """テンプレートから /static/... 参照を抽出"""
    content = template_path.read_text()
    # src="..." や href="..." から /static で始まるパスを抽出
    pattern = r'(?:src|href)=["\'](/static/[^"\']+)["\']'
    return re.findall(pattern, content)


def test_all_static_references_exist():
    """全テンプレートの静的ファイル参照が存在することを確認"""
    missing = []

    for template in TEMPLATES_DIR.glob("*.mustache"):
        refs = extract_static_references(template)
        for ref in refs:
            # /static/xxx -> static/xxx に変換してSTATIC_DIRの親から解決
            relative_path = ref.lstrip("/")  # "static/js/foo.js"
            file_path = STATIC_DIR.parent / relative_path

            if not file_path.exists():
                missing.append(f"{template.name}: {ref}")

    assert not missing, "Missing static files:\n" + "\n".join(missing)


def test_extract_static_references():
    """extract_static_references関数のテスト"""
    # テスト用の一時的な内容
    test_content = """
    <link href="/static/css/styles.css" rel="stylesheet">
    <script src="/static/js/app.js"></script>
    <script src='/static/js/utils.js'></script>
    <img src="/static/images/logo.png" alt="Logo">
    <a href="https://example.com">External</a>
    """

    # Pathオブジェクトのread_textをモックせずに、正規表現を直接テスト
    pattern = r'(?:src|href)=["\'](/static/[^"\']+)["\']'
    refs = re.findall(pattern, test_content)

    assert len(refs) == 4
    assert "/static/css/styles.css" in refs
    assert "/static/js/app.js" in refs
    assert "/static/js/utils.js" in refs
    assert "/static/images/logo.png" in refs


def test_templates_directory_exists():
    """テンプレートディレクトリが存在することを確認"""
    assert TEMPLATES_DIR.exists(), f"Templates directory not found: {TEMPLATES_DIR}"
    assert TEMPLATES_DIR.is_dir(), f"Templates path is not a directory: {TEMPLATES_DIR}"


def test_static_directory_exists():
    """静的ファイルディレクトリが存在することを確認"""
    assert STATIC_DIR.exists(), f"Static directory not found: {STATIC_DIR}"
    assert STATIC_DIR.is_dir(), f"Static path is not a directory: {STATIC_DIR}"
