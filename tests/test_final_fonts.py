"""Public-render regressions for macOS system UI shaping and real missing glyphs."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
TITLE = 'Mobile PDF Layout Research · 2026-06-01'


def render(source, target):
    return subprocess.run(
        [sys.executable, str(ROOT / 'scripts/md2pdf_chrome.py'), str(source), str(target),
         '--theme', 'blue'],
        capture_output=True, text=True, timeout=120)


@pytest.mark.integration
@pytest.mark.parametrize('whole_reference', [False, True], ids=['heading', 'real-reference'])
def test_system_ui_middle_dot_heading_renders(tmp_path, whole_reference):
    if whole_reference:
        source = ROOT / 'references/mobile-layout-research.md'
    else:
        source = tmp_path / 'middle-dot.md'
        source.write_text(f'# {TITLE}\n\nFONT_END\n', encoding='utf-8')
    target = tmp_path / 'middle-dot.pdf'
    result = render(source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = [json.loads(line.partition(':')[2]) for line in result.stderr.splitlines()
               if line.startswith('FONT_REPORT:')]
    assert len(reports) == 1
    report = reports[0]
    assert report['fonts'] and not report['missing'] and not report['lastResort']
    if sys.platform == 'darwin':
        assert any(font['postScriptName'] == '.SFNS-Bold' and font['glyphCount'] > 0
                   for font in report['fonts']), report
        assert 'shaped UI cascade' in report['nativeCoverage']
    text = '\n'.join(page.extract_text() for page in PdfReader(target).pages)
    assert TITLE in text


@pytest.mark.integration
@pytest.mark.parametrize('existing_output', [False, True], ids=['new-output', 'keep-output'])
def test_system_ui_genuine_tofu_still_fails_atomically(tmp_path, existing_output):
    source = tmp_path / 'tofu.md'
    source.write_text(f'# {TITLE} \U0010ffff\n', encoding='utf-8')
    target = tmp_path / 'tofu.pdf'
    original = b'previous accepted output'
    if existing_output:
        target.write_bytes(original)
    result = render(source, target)
    assert result.returncode != 0
    assert 'MISSING_GLYPHS:' in result.stdout + result.stderr
    if existing_output:
        assert target.read_bytes() == original
    else:
        assert not target.exists()
