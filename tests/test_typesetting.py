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
def test_mid_length_code_blocks_split_instead_of_leaving_half_empty_pages(tmp_path):
    """Blocks a bit over half a page must not each be pushed to a fresh page."""
    block = '\n'.join(f'line_{i:02d} = {i}' for i in range(34))  # ≈ 60% of an A4 page
    parts = [f'## Section {n}\n\nSECTION_{n}_START\n\n```python\n{block}\n```\n' for n in range(8)]
    source = tmp_path / 'mid-blocks.md'
    source.write_text('# Density\n\n' + '\n'.join(parts), encoding='utf-8')
    pdf = tmp_path / 'mid-blocks.pdf'
    result = render(source, pdf)
    assert result.returncode == 0, result.stderr
    texts = [p.extract_text() for p in PdfReader(pdf).pages]
    body = '\n'.join(texts)
    assert all(body.count(f'SECTION_{n}_START') == 1 for n in range(8))
    # Eight ~60% blocks fit in about six pages; keeping each whole needs eight.
    assert len(texts) <= 6, len(texts)


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


@pytest.mark.integration
def test_fonts_record_actual_faces_and_preserve_cjk(tmp_path):
    import json
    source = samples(tmp_path)['fonts']
    target = tmp_path / 'fonts.pdf'
    result = render(source, target)
    assert result.returncode == 0, result.stderr
    reports = [json.loads(line.partition(':')[2]) for line in result.stderr.splitlines()
               if line.startswith('FONT_REPORT:')]
    assert len(reports) == 1
    report = reports[0]
    assert report['fonts'] and sum(font['glyphCount'] for font in report['fonts']) > 0
    assert not report['missing'] and not report['lastResort']
    assert 'FONT_END' in PdfReader(target).pages[0].extract_text()


@pytest.mark.integration
def test_missing_glyph_fails_without_output(tmp_path):
    source = tmp_path / 'missing.md'
    source.write_text('# Missing glyph\n\nUnavailable \U0010ffff end.')
    target = tmp_path / 'missing.pdf'
    assert render(source, target).returncode != 0
    assert not target.exists()


@pytest.mark.integration
def test_mermaid_and_images_ready_before_pdf(tmp_path):
    import json
    source = samples(tmp_path)['readiness']
    target = tmp_path / 'ready.pdf'
    result = render(source, target, '--verify-strict')
    assert result.returncode == 0, result.stderr
    reader = PdfReader(target)
    assert reader.metadata['/JZDiagramTotal'] == reader.metadata['/JZDiagramRendered'] == '2'
    body = ''.join(''.join(p.extract_text() for p in reader.pages).split())
    assert 'DIAGRAM_ONE' in body and 'DIAGRAM_TWO' in body and 'READY_END' in body
    image = next(json.loads(line.partition(':')[2]) for line in result.stderr.splitlines()
                 if line.startswith('IMAGE_STAT:'))
    assert image['total'] == len(image['decoded']) == 1
    assert not image['errors']
    assert all(item['width'] > 0 and item['height'] > 0 for item in image['decoded'])


@pytest.mark.integration
def test_diagram_waiver_reports_incomplete_count(tmp_path):
    import json
    source = samples(tmp_path)['bad-diagram']
    target = tmp_path / 'waiver.pdf'
    assert render(source, target).returncode == 3
    assert not target.exists()
    result = render(source, target, '--allow-diagram-errors')
    assert result.returncode == 0, result.stderr
    report = next(json.loads(line.partition(':')[2]) for line in result.stderr.splitlines()
                  if line.startswith('MERMAID_WAIVER:'))
    assert report['total'] == 1 and report['rendered'] == 0 and len(report['errors']) == 1
    reader = PdfReader(target)
    assert reader.metadata['/JZDiagramTotal'] == '1'
    assert reader.metadata['/JZDiagramRendered'] == '0'
