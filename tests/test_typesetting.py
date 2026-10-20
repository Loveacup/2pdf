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


@pytest.mark.integration
def test_tables_repeat_headers_and_reconcile_data(tmp_path):
    source = samples(tmp_path)['tables']
    target = tmp_path / 'tables.pdf'
    result = render(source, target)
    assert result.returncode == 0, result.stderr
    texts = [p.extract_text() for p in PdfReader(target).pages]
    body = ''.join(''.join(texts).split())
    for cols in (3, 6, 8):
        for row in range(3):
            for col in range(cols):
                assert body.count(f'CELL_{cols}_{row}_{col}') == 1
    for i in range(84):
        assert body.count(f'ROW_{i:03d}') == 1
        assert body.count(f'DATA_{i:03d}') == 1
    for i in range(100):
        assert body.count(f'LONG_CELL_{i:03d}') == 1
    long_pages = [text for text in texts if 'ROW_0' in text]
    assert len(long_pages) == 3
    assert all(text.count('REPEATED_HEAD') == 1 for text in long_pages)
    assert all(body.count(marker) == 1 for marker in ('ROWSPAN_CELL', 'SPAN_A', 'SPAN_B'))


@pytest.mark.integration
def test_unreadable_table_fails_without_overwriting(tmp_path):
    source = tmp_path / 'narrow.md'
    source.write_text('<table><tr>' + '<td>content</td>' * 40 + '</tr></table>')
    target = tmp_path / 'kept.pdf'
    target.write_bytes(b'original accepted output')
    assert render(source, target).returncode != 0
    assert target.read_bytes() == b'original accepted output'
