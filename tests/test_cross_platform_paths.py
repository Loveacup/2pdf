"""Regression coverage for Windows and POSIX browser file paths."""
import json
from pathlib import PurePosixPath, PureWindowsPath
from types import SimpleNamespace

import pytest
import md2pdf_chrome as m


@pytest.mark.parametrize("path_type,root", [
    (PureWindowsPath, "C:/Users/Test User"),
    (PurePosixPath, "/Users/Test User"),
])
def test_pdf_script_escapes_paths(monkeypatch, path_type, root):
    html_path = path_type(root) / "中文 'input'.html"
    pdf_path = path_type(root) / "中文 'output'.pdf"
    captured = []

    class FakePath:
        def __init__(self, value):
            self.value = value
        def resolve(self):
            return self.value
        def read_text(self, **kwargs):
            return "<html></html>"
        def exists(self):
            return True
        def stat(self):
            return SimpleNamespace(st_size=2048)

    class ScriptPath:
        def __truediv__(self, name):
            return self
        def write_text(self, text, **kwargs):
            captured.append(text)
        def __str__(self):
            return "mock-render.js"

    monkeypatch.setattr(m, "Path", lambda _: ScriptPath())
    monkeypatch.setattr(m, "_node_env", lambda: {})
    monkeypatch.setattr(m, "_launch_plan", lambda _: [("chromium.launch()", "mock", "mock")])
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="OK", stderr=""))
    m._render_playwright(FakePath(html_path), FakePath(pdf_path))
    script = captured[0]
    assert f"page.goto({json.dumps(html_path.as_uri())}," in script
    assert f"path: {json.dumps(str(pdf_path))}," in script


def test_png_script_escapes_paths(monkeypatch, tmp_path):
    html = tmp_path / "中文 'input'.html"
    output = tmp_path / "中文 'output'.png"
    html.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(m.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(m, "_launch_plan", lambda _: [("chromium.launch()", "mock", "mock")])

    def run(*args, **kwargs):
        output.write_bytes(b"mock png")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(m.subprocess, "run", run)
    m._render_playwright_output(html, output, "png")
    script = (tmp_path / "pw_render_output.js").read_text(encoding="utf-8")
    assert f"page.goto({json.dumps(html.as_uri())}," in script
    assert f"path: {json.dumps(str(output))}," in script


def test_inline_css_reads_local_file_uri(tmp_path):
    stylesheet = tmp_path / "中文 'style'.css"
    stylesheet.write_text("p { color: red; }", encoding="utf-8")
    html = f'<html><head><link rel="stylesheet" href="{stylesheet.as_uri()}"></head><body><p>test</p></body></html>'
    result = m.inline_css(html)
    assert 'style="color: red;"' in result
    assert stylesheet.as_uri() not in result


def test_local_vendor_urls_are_file_uris(monkeypatch, tmp_path):
    vendor = tmp_path / "中文 'vendor'.js"
    vendor.write_text("// local", encoding="utf-8")
    monkeypatch.setattr(m, "MERMAID_LOCAL", vendor)
    monkeypatch.setattr(m, "HLJS_LOCAL", vendor)
    assert m.get_mermaid_src() == vendor.as_uri()
    assert m._hljs_js_src() == vendor.as_uri()
    html = '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
    assert vendor.as_uri() in m._localize_mermaid_src(html)
