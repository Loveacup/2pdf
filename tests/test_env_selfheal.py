"""M2 环境自愈单测：venv 路径跨平台分支 / vendor pin 常量 / 平台提示。"""
import sys
import json
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import md2pdf_chrome as m  # noqa: E402


def test_venv_python_posix():
    with mock.patch.object(sys, "platform", "darwin"):
        assert m._venv_python().parts[-2:] == ("bin", "python")


def test_venv_python_windows():
    with mock.patch.object(sys, "platform", "win32"):
        p = str(m._venv_python())
        assert p.endswith("python.exe") and "Scripts" in p


def test_pandoc_hint_per_platform():
    with mock.patch.object(sys, "platform", "darwin"):
        assert "brew" in m._pandoc_install_hint()
    with mock.patch.object(sys, "platform", "win32"):
        assert "winget" in m._pandoc_install_hint()
    with mock.patch.object(sys, "platform", "linux"):
        assert "apt" in m._pandoc_install_hint()


def test_vendor_pins_are_exact():
    """pin 必须是精确三段版本号，不许 @11 浮动。"""
    import re
    assert re.fullmatch(r"\d+\.\d+\.\d+", m.MERMAID_PIN)
    assert re.fullmatch(r"\d+\.\d+\.\d+", m.HLJS_PIN)
    assert m.MERMAID_PIN in m.MERMAID_CDN
    assert m.HLJS_PIN in m.HLJS_CDN


def test_mermaid_local_not_in_tmp():
    """M2.4 X4：vendor 副本必须持久存 scripts/ 旁，不许 /tmp。"""
    assert "/tmp/" not in str(m.MERMAID_LOCAL)
    assert m.MERMAID_LOCAL.parent == m.SCRIPTS_DIR


def test_vendor_lock_written(tmp_path):
    fake = tmp_path / "x.js"
    fake.write_text("console.log(1)")
    with mock.patch.object(m, "VENDOR_LOCK", tmp_path / "vendor.lock.json"):
        m._record_vendor("demo", "1.2.3", fake)
        lock = json.loads((tmp_path / "vendor.lock.json").read_text())
    assert lock["demo"]["version"] == "1.2.3"
    assert len(lock["demo"]["sha256"]) == 64


def test_find_system_chrome_windows_candidates():
    with mock.patch.object(sys, "platform", "win32"), \
         mock.patch.dict("os.environ", {"PROGRAMFILES": r"C:\Program Files"}), \
         mock.patch("os.path.exists", return_value=False), \
         mock.patch("shutil.which", return_value=None):
        assert m._find_system_chrome() is None  # 不炸即分支覆盖


def _fake_node(node_version, playwright_version):
    def run(cmd, **_kw):
        out = node_version if "--version" in cmd else playwright_version
        return mock.Mock(returncode=0 if out else 1, stdout=out or "")
    return run


def test_playwright_install_blocker_version_boundary():
    """Playwright <1.60 + Node ≥24.16 会在解压时挂死：setup 必须拒绝；边界外放行。"""
    cases = [
        (("v26.12.0", "1.58.2"), True),
        (("v24.16.0", "1.59.9"), True),
        (("v24.15.0", "1.58.2"), False),
        (("v26.12.0", "1.60.0"), False),
        (("v26.12.0", None), False),  # 本地无 playwright：npx 会取最新版
    ]
    for (node_v, pw_v), blocked in cases:
        with mock.patch("shutil.which", return_value="/usr/bin/node"), \
             mock.patch.object(m.subprocess, "run", side_effect=_fake_node(node_v, pw_v)):
            assert (m._playwright_install_blocker() is not None) is blocked, (node_v, pw_v)
