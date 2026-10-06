#!/usr/bin/env python3
"""Initialize 2pdf's existing environment and report dependency update reminders."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.parse import quote
import urllib.request

SCRIPTS = Path(__file__).resolve().parent
RENDERER = SCRIPTS / "md2pdf_chrome.py"
VENV = Path.home() / ".venvs" / "pdf-skill"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PYTHON_PACKAGES = ("markdown", "pypdf", "PyYAML", "css-inline")
JS_PACKAGES = ("mermaid", "highlight.js", "playwright")


def _version_tuple(value: str) -> tuple[tuple[int, ...], tuple[int, int]]:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)(.*)$", value)
    if not match:
        return (0,), (4, 0)
    nums = tuple(int(part) for part in match.group(1).split("."))
    suffix = match.group(2).lower().split("+", 1)[0]
    if suffix.startswith((".post", "post")):
        rank = 5
    elif suffix.startswith((".dev", "dev")):
        rank = 0
    elif suffix.startswith((".a", "a", ".alpha", "alpha")):
        rank = 1
    elif suffix.startswith((".b", "b", ".beta", "beta")):
        rank = 2
    elif suffix.startswith((".rc", "rc", "-", ".pre", "pre")):
        rank = 3
    else:
        rank = 4
    stage = re.search(r"(\d+)", suffix)
    return nums, (rank, int(stage.group(1)) if stage else 0)


def _newer(latest: str, current: str) -> bool:
    latest_nums, latest_stage = _version_tuple(latest)
    current_nums, current_stage = _version_tuple(current)
    width = max(len(latest_nums), len(current_nums))
    a = latest_nums + (0,) * (width - len(latest_nums))
    b = current_nums + (0,) * (width - len(current_nums))
    return (a, latest_stage) > (b, current_stage)


def _python_current() -> dict[str, str]:
    if not VENV_PYTHON.is_file():
        return {}
    code = (
        "import importlib.metadata as m,json,sys; from pathlib import Path; "
        "expected=Path(sys.argv[1]).resolve(); names=('markdown','pypdf','PyYAML','css-inline'); out={}\n"
        "if Path(sys.prefix).resolve()!=expected or sys.prefix==sys.base_prefix:\n"
        " print('{}')\n"
        "else:\n"
        " for n in names:\n"
        "  try: out[n]=m.version(n)\n"
        "  except m.PackageNotFoundError: pass\n"
        " print(json.dumps(out))"
    )
    try:
        proc = subprocess.run([str(VENV_PYTHON), "-I", "-c", code, str(VENV)],
                              capture_output=True, text=True, timeout=15, check=False)
        if proc.returncode == 0:
            result = json.loads(proc.stdout)
            return result if isinstance(result, dict) else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {}


def _node_current() -> dict[str, str]:
    node = shutil.which("node")
    if not node:
        return {}
    env = dict(os.environ)
    module_paths = [Path.home() / "node_modules", Path("/usr/local/lib/node_modules")]
    found = [str(path) for path in module_paths if path.exists()]
    if found:
        env["NODE_PATH"] = os.pathsep.join(filter(None, [env.get("NODE_PATH"), *found]))
    code = "const out={};for(const n of ['playwright']){try{const p=require.resolve(n+'/package.json');out[n]=require(p).version}catch{}};process.stdout.write(JSON.stringify(out))"
    try:
        proc = subprocess.run([node, "-e", code], capture_output=True, text=True,
                              timeout=15, env=env, check=False)
        if proc.returncode == 0:
            result = json.loads(proc.stdout)
            return result if isinstance(result, dict) else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {}
def _official_latest(ecosystem: str, package: str) -> str:
    if ecosystem == "pypi":
        url = f"https://pypi.org/pypi/{package}/json"
    else:
        url = f"https://registry.npmjs.org/{package}/latest"
    request = urllib.request.Request(url, headers={"User-Agent": "2pdf-maintenance/1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    latest = payload.get("info", {}).get("version") if ecosystem == "pypi" else payload.get("version")
    if not isinstance(latest, str) or not latest:
        raise ValueError("official registry response has no latest version")
    return latest


def _vendor_current() -> dict[str, str]:
    lock_path = SCRIPTS / "vendor.lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result = {}
    for name, info in lock.items():
        if name not in ("mermaid", "highlight.js") or not isinstance(info, dict):
            continue
        filename, version, expected = info.get("file"), info.get("version"), info.get("sha256")
        if not all(isinstance(value, str) and value for value in (filename, version, expected)):
            continue
        try:
            digest = hashlib.sha256((SCRIPTS / filename).read_bytes()).hexdigest()
        except OSError:
            continue
        if digest == expected:
            result[name] = version
    return result


def _vendor_pins() -> dict[str, str]:
    try:
        lock = json.loads((SCRIPTS / "vendor.lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {name: info["version"] for name, info in lock.items()
            if name in ("mermaid", "highlight.js") and isinstance(info, dict)
            and isinstance(info.get("version"), str)}


def _rows() -> tuple[list[dict], bool]:
    py_current = _python_current()
    node_current = _node_current()
    current = {**py_current, **_vendor_current(), **node_current}
    pins = _vendor_pins()
    specs = [("python", "pypi", name) for name in PYTHON_PACKAGES]
    specs.extend(("npm", "npm", name) for name in JS_PACKAGES)
    rows = []
    metadata_failed = False
    for ecosystem, registry, name in specs:
        current_version = current.get(name)
        row = {
            "name": name,
            "source": "PyPI" if registry == "pypi" else "npm",
            "current": current_version,
            "pinned": pins.get(name),
            "latest": None,
            "status": "unavailable",
            "update_available": False,
            "url": (f"https://pypi.org/project/{quote(name)}/" if registry == "pypi"
                    else f"https://www.npmjs.com/package/{quote(name, safe='@')}"),
        }
        try:
            latest = _official_latest(registry, name)
            row["latest"] = latest
            comparison_version = current_version or pins.get(name)
            if comparison_version is not None:
                row["update_available"] = _newer(latest, comparison_version)
                row["status"] = "update_available" if row["update_available"] else "available"
            else:
                metadata_failed = True
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError,
                TypeError, json.JSONDecodeError, UnicodeError):
            metadata_failed = True
        rows.append(row)
    return rows, metadata_failed


def check_updates(as_json: bool = False) -> int:
    rows, unavailable = _rows()
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall": "unavailable" if unavailable else "ok",
        "updates": rows,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("2pdf dependency update check (reminders only; nothing is installed)")
        for row in rows:
            if row["status"] == "unavailable":
                latest = f"; latest {row['latest']}" if row["latest"] else ""
                print(f"- {row['name']}: unavailable (installed version or official metadata missing){latest}")
            elif row["update_available"]:
                print(f"- {row['name']}: update available ({row['current']} → {row['latest']}); update explicitly when ready")
            else:
                print(f"- {row['name']}: current {row['current']} (latest {row['latest']})")
        if unavailable:
            print("One or more dependency versions could not be verified; this check is incomplete.",
                  file=sys.stderr)
    return 1 if unavailable else 0


def _isolated_venv() -> bool:
    if not VENV_PYTHON.is_file():
        return False
    code = (
        "import sys; from pathlib import Path; expected=Path(sys.argv[1]).resolve(); "
        "cfg={line.split('=',1)[0].strip():line.split('=',1)[1].strip() "
        "for line in (expected/'pyvenv.cfg').read_text().splitlines() if '=' in line}\n"
        "sys.exit(0 if Path(sys.prefix).resolve()==expected and sys.prefix!=sys.base_prefix "
        "and cfg.get('include-system-site-packages','true').strip().lower()=='false' else 1)"
    )
    try:
        result = subprocess.run([str(VENV_PYTHON), "-I", "-c", code, str(VENV)],
                                capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _healthy_venv() -> bool:
    if not _isolated_venv():
        return False
    code = "import importlib.util,sys;sys.exit(0 if all(importlib.util.find_spec(n) for n in ('markdown','pypdf','yaml')) else 1)"
    try:
        result = subprocess.run([str(VENV_PYTHON), "-I", "-c", code],
                                capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _nonempty_nonvenv() -> bool:
    if VENV.is_symlink() and not VENV.exists():
        return True
    if not VENV.exists():
        return False
    if _isolated_venv():
        return False
    try:
        return not VENV.is_dir() or next(VENV.iterdir(), None) is not None
    except OSError:
        return True


def _preflight_status() -> dict[str, str] | None:
    try:
        result = subprocess.run([sys.executable, str(RENDERER), "--preflight", "--json"],
                                capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        report = json.loads(result.stdout)
        checks = report.get("checks")
        if not isinstance(checks, list):
            return None
        return {check["name"]: check["status"] for check in checks
                if isinstance(check, dict) and isinstance(check.get("name"), str)
                and isinstance(check.get("status"), str)}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
        return None


def _required_resources_ready() -> bool:
    checks = _preflight_status()
    required = ("playwright:bundled", "mermaid-vendor", "hljs-vendor")
    return checks is not None and all(checks.get(name) == "ok" for name in required)


def init() -> int:
    print(f"2pdf environment: {VENV}")
    if _healthy_venv() and _required_resources_ready():
        print("Healthy persistent environment and required browser/vendor resources already exist; no setup run.")
        return 0
    if _nonempty_nonvenv():
        print(f"Setup refused: existing path is nonempty and is not an isolated venv: {VENV}",
              file=sys.stderr)
        return 1
    if not RENDERER.is_file():
        print(f"Setup failed: renderer not found: {RENDERER}", file=sys.stderr)
        return 1
    if _preflight_status() is None:
        print("Setup refused: renderer preflight did not return valid JSON; environment state is unknown.",
              file=sys.stderr)
        return 1
    print("Environment or required browser/vendor resources are missing; invoking explicit --setup.")
    print("The legacy workflow may install missing Python packages, download Chromium/vendor assets, and run a smoke render.")
    try:
        result = subprocess.run([sys.executable, str(RENDERER), "--setup"], check=False)
    except OSError as exc:
        print(f"Setup failed to start: {exc}", file=sys.stderr)
        return 1
    if result.returncode:
        print(f"Setup failed with exit code {result.returncode}.", file=sys.stderr)
        return result.returncode
    if not _isolated_venv() or not _healthy_venv():
        print("Setup completed but the persistent Python environment failed isolation/dependency checks.",
              file=sys.stderr)
        return 1
    if not _required_resources_ready():
        print("Setup completed but required Playwright Chromium or bundled assets remain unavailable.",
              file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize 2pdf and check dependency update reminders.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="reuse a healthy venv or invoke the renderer's explicit setup")
    updates = subparsers.add_parser("check-updates", help="query official package metadata; never install updates")
    updates.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    if args.command == "init":
        return init()
    return check_updates(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
