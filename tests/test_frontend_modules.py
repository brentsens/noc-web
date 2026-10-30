import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


FRONTEND = Path(__file__).parents[1] / "frontend"
MODULE_SCRIPT_PATTERN = re.compile(
    r'<script\s+type=["\']module["\']\s*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
NAMED_IMPORT_PATTERN = re.compile(
    r'import\s*\{(?P<names>[^}]+)\}\s*from\s*["\'](?P<path>[^"\']+)["\']',
)
NAMED_EXPORT_PATTERN = re.compile(
    r'export\s+(?:async\s+)?function\s+(?P<function>[A-Za-z_$][\w$]*)'
    r'|export\s*\{(?P<names>[^}]+)\}',
)


def _names(clause: str) -> set[str]:
    return {
        name.strip().split(" as ")[0].strip()
        for name in clause.split(",")
        if name.strip()
    }


def _exports(module: Path) -> set[str]:
    exports = set()
    for match in NAMED_EXPORT_PATTERN.finditer(module.read_text(encoding="utf-8")):
        if match.group("function"):
            exports.add(match.group("function"))
        else:
            exports.update(_names(match.group("names")))
    return exports


def test_browser_module_sources_have_valid_es_module_syntax():
    modules = (FRONTEND / "js" / "api.js", FRONTEND / "js" / "workflow-context.js")
    for module in modules:
        result = subprocess.run(
            ["node", "--check", "--input-type=module"],
            input=module.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_html_module_scripts_have_valid_es_module_syntax_and_resolved_named_imports():
    checked_pages = 0
    for page in FRONTEND.glob("*.html"):
        scripts = MODULE_SCRIPT_PATTERN.findall(page.read_text(encoding="utf-8"))
        imports = [
            match
            for script in scripts
            for match in NAMED_IMPORT_PATTERN.finditer(script)
            if urlsplit(match.group("path")).path in {
                "./js/api.js",
                "./js/workflow-context.js",
            }
        ]
        if not imports:
            continue

        checked_pages += 1
        for script in scripts:
            result = subprocess.run(
                ["node", "--check", "--input-type=module"],
                input=script,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, f"{page}: {result.stderr}"

        for imported in imports:
            module = (page.parent / urlsplit(imported.group("path")).path).resolve()
            missing = _names(imported.group("names")) - _exports(module)
            assert not missing, f"{page}: {module.name} does not export {sorted(missing)}"

    assert checked_pages > 0
