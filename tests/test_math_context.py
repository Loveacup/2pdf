"""Source-context and final-DOM regressions from the P1 static review."""
import json
from html.parser import HTMLParser

import pytest
from pypdf import PdfReader

from code_spans import protect_code_spans
from math_rendering import extract_math, source_formula_count
from md2pdf_chrome import build_html
from test_typesetting import render


class MathDOM(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.annotations = []
        self._annotation = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href'))
        if tag == 'annotation':
            self._annotation = True

    def handle_endtag(self, tag):
        if tag == 'annotation':
            self._annotation = False

    def handle_data(self, data):
        if self._annotation:
            self.annotations.append(data)


@pytest.mark.parametrize('source, expected', [
    ('Prices $5 and $10; let $x$ be positive.', ['x']),
    ('> $$\n> x^2\n> $$', ['\nx^2\n']),
    ('> [!note]\n> $$\n> x > 0\n> $$', ['\nx > 0\n']),
    ('> > $$\n> > x > 0\n> > $$', ['\nx > 0\n']),
    ('> Let $x\n> > 0$ be positive.', ['x\n> 0']),
    ('$$\n> x\n$$', ['\n> x\n']),
])
def test_math_recognition_respects_price_and_quote_boundaries(source, expected):
    protected, _ = protect_code_spans(source)
    _, formulas = extract_math(protected)
    assert [item['source'] for item in formulas] == expected
    assert source_formula_count(source) == len(expected)


def test_heading_anchor_uses_stable_source_text(tmp_path):
    source = tmp_path / 'anchors.md'
    source.write_text('[Jump](#equation-x2)\n\n[TOC]\n\n# Equation $x^2$\n')
    for _ in range(2):
        dom = MathDOM()
        dom.feed(build_html(source, '', theme='blue'))
        assert dom.ids == ['equation-x2']
        assert dom.links.count('#equation-x2') == 2


@pytest.mark.integration
@pytest.mark.parametrize('source, expected', [
    ('Prices $5 and $10; let $x$ be positive.\n', ['x']),
    ('> [!note]\n> $$\n> x > 0\n> $$\n', ['\nx > 0\n']),
    ('> $$\n> x^2\n> $$\n', ['\nx^2\n']),
])
def test_context_formulas_render_exact_source_in_exported_html(tmp_path, source, expected):
    md = tmp_path / 'context.md'
    md.write_text(source)
    html = tmp_path / 'context.html'
    result = render(md, html, '--format', 'html')
    assert result.returncode == 0, result.stderr
    dom = MathDOM()
    dom.feed(html.read_text())
    assert dom.annotations == expected
    if source.startswith('Prices'):
        assert 'Prices $5 and $10; let ' in html.read_text()


@pytest.mark.integration
def test_mobile_cards_preserve_heading_and_title_formula_nodes(tmp_path):
    md = tmp_path / 'mobile.md'
    md.write_text('| Formula | $a^2$ | C | D | E | F |\n'
                  '|---|---|---|---|---|---|\n'
                  '| $x^2$ | $y^2$ | 3 | 4 | 5 | 6 |\n')
    html = tmp_path / 'mobile.html'
    result = render(md, html, '--format', 'html', '--page-size', '430x932')
    assert result.returncode == 0, result.stderr
    dom = MathDOM()
    dom.feed(html.read_text())
    assert dom.annotations == ['x^2', 'a^2', 'y^2']
    assert 'wide-table-card-title' in html.read_text()
    assert '<table' not in html.read_text()
    stat = next(line for line in result.stderr.splitlines() if line.startswith('MATH_STAT:'))
    assert json.loads(stat.partition(':')[2]) == {'total': 3, 'rendered': 3}
    pdf = tmp_path / 'mobile.pdf'
    result = render(md, pdf, '--page-size', '430x932', '--verify-strict')
    assert result.returncode == 0, result.stderr
    metadata = PdfReader(pdf).metadata
    assert metadata['/JZMathTotal'] == metadata['/JZMathRendered'] == '3'


@pytest.mark.integration
def test_exported_heading_anchor_keeps_authored_link_target(tmp_path):
    source = tmp_path / 'anchors.md'
    source.write_text('[Jump](#equation-x2)\n\n# Equation $x^2$\n')
    for i in range(2):
        html = tmp_path / f'anchors-{i}.html'
        result = render(source, html, '--format', 'html')
        assert result.returncode == 0, result.stderr
        dom = MathDOM()
        dom.feed(html.read_text())
        assert dom.ids == ['equation-x2']
        assert dom.links == ['#equation-x2']
        assert dom.annotations == ['x^2']


@pytest.mark.integration
def test_final_dom_reconciliation_rejects_removed_formula(tmp_path, monkeypatch):
    import md2pdf_chrome

    source = tmp_path / 'formula.md'
    source.write_text('$x^2$\n')
    target = tmp_path / 'formula.html'
    original_assets = md2pdf_chrome.math_assets

    def removing_assets(formulas):
        return original_assets(formulas) + '''<script>
document.addEventListener('DOMContentLoaded', function() {
  document.querySelector('.jz-math').remove();
});
</script>'''

    monkeypatch.setattr(md2pdf_chrome, 'math_assets', removing_assets)
    with pytest.raises(md2pdf_chrome.MathRenderError, match='Formula count changed in final DOM'):
        md2pdf_chrome.md_to_output(source, target, fmt='html')
    assert not target.exists()


@pytest.mark.integration
def test_bad_formula_reports_one_structured_error(tmp_path, monkeypatch):
    import md2pdf_chrome

    source = tmp_path / 'bad-formula.md'
    tex = r'\notarealcommand{a}'
    source.write_text(f'${tex}$\n')
    target = tmp_path / 'bad-formula.html'
    errors = []
    original_formatter = md2pdf_chrome.format_math_errors

    def recording_formatter(stderr):
        record = next(line.partition(':')[2] for line in stderr.splitlines()
                      if line.startswith('MATH_ERRORS:'))
        errors.extend(json.loads(record))
        return original_formatter(stderr)

    monkeypatch.setattr(md2pdf_chrome, 'format_math_errors', recording_formatter)
    with pytest.raises(md2pdf_chrome.MathRenderError):
        md2pdf_chrome.md_to_output(source, target, fmt='html')
    assert len(errors) == 1
    assert errors[0]['index'] == 1
    assert errors[0]['head'] == tex
    assert not target.exists()
