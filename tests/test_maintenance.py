import json
from pathlib import Path
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import maintenance


def test_init_refuses_system_site_packages_but_accepts_isolated_venv(tmp_path, monkeypatch):
    import venv

    target = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(target)
    python = target / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    monkeypatch.setattr(maintenance, "VENV", target)
    monkeypatch.setattr(maintenance, "VENV_PYTHON", python)
    assert maintenance._isolated_venv()
    assert not maintenance._nonempty_nonvenv()
    cfg = target / "pyvenv.cfg"
    cfg.write_text(cfg.read_text().replace("include-system-site-packages = false",
                                          "include-system-site-packages = true"))
    assert maintenance.init() == 1


def test_init_refuses_nonvenv_without_mutation(tmp_path, monkeypatch):
    target = tmp_path / "environment"
    target.mkdir()
    marker = target / "user-file"
    marker.write_bytes(b"preserve")
    monkeypatch.setattr(maintenance, "VENV", target)
    monkeypatch.setattr(maintenance, "VENV_PYTHON", target / "bin/python")
    assert maintenance.init() == 1
    assert list(target.iterdir()) == [marker]
    assert marker.read_bytes() == b"preserve"


def test_bootstrap_reuses_isolated_environment_without_upgrading(tmp_path, monkeypatch):
    import subprocess
    import venv
    import md2pdf_chrome as renderer

    target = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(target)
    python = target / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    site = Path(subprocess.check_output(
        [str(python), "-I", "-c", "import sysconfig;print(sysconfig.get_path('purelib'))"],
        text=True).strip())
    for name in ("markdown", "pypdf", "PyYAML", "css-inline"):
        dist = site / (name.replace("-", "_") + "-1.0.dist-info")
        dist.mkdir()
        (dist / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n")
    monkeypatch.setattr(renderer, "VENV_DIR", target)
    run = subprocess.run

    def no_installer(command, **kwargs):
        assert "pip" not in command
        return run(command, **kwargs)

    monkeypatch.setattr(renderer.subprocess, "run", no_installer)
    assert renderer._bootstrap_venv() == python


def test_metadata_failure_is_unavailable_and_nonzero(capsys):
    current = {name: "1.0.0" for name in maintenance.PYTHON_PACKAGES}
    current.update({"mermaid": "1.0.0", "highlight.js": "1.0.0", "playwright": "1.0.0"})

    def fail_registry(_ecosystem, _package):
        raise OSError("offline")

    with mock.patch.object(maintenance, "_python_current", return_value=current), \
         mock.patch.object(maintenance, "_vendor_current", return_value={}), \
         mock.patch.object(maintenance, "_node_current", return_value={}), \
         mock.patch.object(maintenance, "_official_latest", side_effect=fail_registry):
        assert maintenance.check_updates(as_json=True) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == 1
    assert report["overall"] == "unavailable"
    row = next(item for item in report["updates"] if item["name"] == "markdown")
    assert row["status"] == "unavailable"
    assert row["current"] == "1.0.0"
    assert row["latest"] is None
    assert row["update_available"] is False


def test_update_report_compares_installed_with_official_latest(capsys):
    current = {name: "1.0.0" for name in maintenance.PYTHON_PACKAGES}
    current.update({"mermaid": "1.0.0", "highlight.js": "1.0.0", "playwright": "1.0.0"})
    latest = {name: "1.0.0" for name in (*maintenance.PYTHON_PACKAGES, *maintenance.JS_PACKAGES)}
    latest["markdown"] = "2.0.0"
    with mock.patch.object(maintenance, "_python_current", return_value=current), \
         mock.patch.object(maintenance, "_vendor_current", return_value={}), \
         mock.patch.object(maintenance, "_node_current", return_value={}), \
         mock.patch.object(maintenance, "_official_latest",
                           side_effect=lambda _ecosystem, name: latest[name]):
        assert maintenance.check_updates(as_json=True) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == 1
    assert report["overall"] == "ok"
    markdown = next(item for item in report["updates"] if item["name"] == "markdown")
    assert (markdown["current"], markdown["latest"], markdown["update_available"],
            markdown["status"], markdown["source"], markdown["pinned"]) == (
                "1.0.0", "2.0.0", True, "update_available", "PyPI", None)
 
def test_version_comparison_orders_prerelease_and_postrelease():
    assert maintenance._newer("2.1.0", "2.1.0rc2")
    assert not maintenance._newer("2.1.0", "2.1.0.post1")

def test_version_comparison_handles_patch_and_equal_releases():
    assert maintenance._newer("2.1.0", "2.0.9")
    assert not maintenance._newer("2.1.0", "2.1")
