"""P1 semantic/content regressions; visual acceptance is recorded separately."""
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader
from p1_samples import samples

ROOT = Path(__file__).resolve().parent.parent


def render(source, target, *flags):
    return subprocess.run([sys.executable, str(ROOT / 'scripts/md2pdf_chrome.py'),
                           str(source), str(target), '--theme', 'blue', *flags],
                          capture_output=True, text=True)


@pytest.mark.integration
def test_semantic_pagination_preserves_long_blocks_and_heading_pair(tmp_path):
    source = samples(tmp_path)['pagination']
    structures = []
    for i in range(2):
        pdf = tmp_path / f'repeat-{i}.pdf'
        result = render(source, pdf)
        assert result.returncode == 0, result.stderr
        texts = [p.extract_text() for p in PdfReader(pdf).pages]
        structures.append(texts)
        assert any('HEADING_PAIR' in t and 'FIRST_CONTENT' in t for t in texts)
        body = '\n'.join(texts)
        for marker in ('LONG_PARAGRAPH_BEGIN', 'LONG_PARAGRAPH_END', 'FOOTNOTE_VISIBLE',
                       'MANUAL_BREAK_END', 'SHORT_CELL'):
            assert body.count(marker) == 1
        for i in range(90):
            assert body.count(f'CODE_{i:03d}') == 1
        for i in range(80):
            assert body.count(f'CALLOUT_{i:03d}') == 1
        assert 'MANUAL_BREAK_END' in texts[-1]
    assert structures[0] == structures[1]
