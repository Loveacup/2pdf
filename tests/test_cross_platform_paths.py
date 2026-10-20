"""Behavioral coverage for spaces, Unicode, quotes and decoded file paths."""
import base64
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
import md2pdf_chrome as m
from resource_policy import ResourcePolicy
from test_content_preservation import bitmap_bytes


def test_local_resources_decode_paths(tmp_path):
    image = tmp_path / "中文 'image'.png"
    image.write_bytes(bitmap_bytes())
    policy = ResourcePolicy(tmp_path / 'source.md')
    expected = base64.b64encode(image.read_bytes()).decode()
    assert expected in policy.resource(quote(image.name))
    assert expected in policy.resource(image.as_uri())


def test_inline_css_uses_authorized_frozen_stylesheet(tmp_path):
    stylesheet = tmp_path / "中文 'style'.css"
    stylesheet.write_text('p { color: red; }', encoding='utf-8')
    policy = ResourcePolicy(tmp_path / 'source.md')
    html = policy.html(f'<html><head><link rel="stylesheet" href="{stylesheet.as_uri()}"></head><body><p>test</p></body></html>')
    result = m.inline_css(html)
    assert 'style="color: red;"' in result
    assert stylesheet.as_uri() not in result


@pytest.mark.integration
@pytest.mark.parametrize('fmt', ['pdf', 'png'])
def test_cli_unicode_and_quoted_paths(tmp_path, fmt):
    folder = tmp_path / "中文 'folder'"
    folder.mkdir()
    source = folder / "中文 'input'.md"
    source.write_text('# Unicode Path Sentinel\n\n中文路径', encoding='utf-8')
    output = folder / ("中文 'output'." + fmt)
    proc = subprocess.run([sys.executable, str(Path(m.__file__)), str(source), str(output),
                           '--format', fmt, '--browser', 'auto'], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert output.read_bytes().startswith(b'%PDF-' if fmt == 'pdf' else b'\x89PNG\r\n\x1a\n')
