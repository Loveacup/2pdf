"""Dollar-delimiter behavior, offline integrity, formula failures and PDF reconciliation."""
from html.parser import HTMLParser

import pytest
from pypdf import PdfReader, PdfWriter

from math_rendering import extract_math, source_formula_count, vendor_bytes, katex_manifest
from code_spans import protect_code_spans
from resource_policy import ResourceError
from p1_samples import samples
from test_typesetting import render
import verify_pdf


@pytest.mark.parametrize('source, expected', [
    ('$x_i^2$', [('x_i^2', False)]),
    ('$$\\frac{1}{2}$$', [('\\frac{1}{2}', True)]),
    ('$$\n\\sqrt{x}\n$$', [('\n\\sqrt{x}\n', True)]),
    ('$ x$ and $y $', []),
    ('<span title=\"$notMath$\">$yes$</span>', [('yes', False)]),
    ('<code>$code$</code> $real$', [('real', False)]),
    ('[link](https://example.invalid/$notMath$) $yes$', [('yes', False)]),
    ('Price $20 and $30.', []),
    (r'Literal \$x\$ and $y$', [('y', False)]),
    ('$x$2', []),
    ('$x$ 2', [('x', False)]),
    ('`$code$` and $real$', [('real', False)]),
    ('```tex\n$$code$$\n```\n\n$real$', [('real', False)]),
    ('~~~tex\n$code$\n~~~\n\n$real$', [('real', False)]),
    ('---\ntitle: $notMath$\n---\n\n$x$', [('x', False)]),
    ('$unclosed', []),
])
def test_dollar_rules_protect_code_and_prices(source, expected):
    protected, _ = protect_code_spans(source)
    _, formulas = extract_math(protected)
    assert [(item['source'], item['display']) for item in formulas] == expected
    assert source_formula_count(source) == len(expected)


def test_escaped_dollar_becomes_literal_without_changing_code():
    protected, store = protect_code_spans(r'Price \$5 and `\$code`')
    text, formulas = extract_math(protected)
    assert not formulas
    assert r'\$code' in store[0]
    assert 'Price $5' in text


def test_math_vendor_manifest_bytes_are_pinned():
    manifest = katex_manifest()
    for name in manifest:
        assert vendor_bytes(name, manifest)
    assert len([name for name in manifest if name.startswith('katex-font:')]) == 20


def test_missing_or_tampered_math_vendor_is_rejected(tmp_path, monkeypatch):
    import math_rendering
    monkeypatch.setattr(math_rendering, 'SCRIPTS', tmp_path)
    manifest = {'demo': {'file': 'katex/x.js', 'sha256': '0' * 64}}
    with pytest.raises(ResourceError):
        vendor_bytes('demo', manifest)
    (tmp_path / 'katex').mkdir()
    (tmp_path / 'katex/x.js').write_bytes(b'tampered')
    with pytest.raises(ResourceError):
        vendor_bytes('demo', manifest)


@pytest.mark.integration
def test_formula_pdf_reconciles_source_metadata_and_fails_tampering(tmp_path):
    source = samples(tmp_path)['math']
    target = tmp_path / 'math.pdf'
    result = render(source, target, '--verify-strict')
    assert result.returncode == 0, result.stderr
    reader = PdfReader(target)
    assert reader.metadata['/JZMathTotal'] == reader.metadata['/JZMathRendered'] == '4'
    check = next(item for item in verify_pdf.verify(target, source)['checks'] if item['name'] == 'math_count')
    assert check['status'] == 'passed'
    body = '\n'.join(page.extract_text() for page in reader.pages)
    assert 'MATH_END' in body and '$code$' in body and '$$not_formula$$' in body
    assert '\\$5' not in body and '$5' in body
    writer = PdfWriter(clone_from=reader)
    writer.add_metadata({'/JZMathRendered': '3'})
    wrong = tmp_path / 'wrong.pdf'
    writer.write(wrong)
    assert verify_pdf.failed(verify_pdf.verify(wrong, source), strict=True)
    # Equal but wrong totals must not bypass the source parser count.
    writer.add_metadata({'/JZMathRendered': '3', '/JZMathTotal': '3'})
    writer.write(wrong)
    assert verify_pdf.failed(verify_pdf.verify(wrong, source), strict=True)


@pytest.mark.integration
@pytest.mark.parametrize('tex', [r'\notAFunction{x}', r'\frac{1}', r'\href{javascript:alert(1)}{click}',
                                 r'\htmlClass{injected}{x}', r'\includegraphics{http://127.0.0.1:9/x.png}'])
def test_formula_errors_do_not_fallback_or_overwrite(tmp_path, tex):
    source = tmp_path / 'bad.md'
    source.write_text('First $x^2$.\n\nBad $' + tex + '$.\n')
    target = tmp_path / 'kept.pdf'
    target.write_bytes(b'accepted original')
    result = render(source, target, '--browser', 'auto')
    assert result.returncode == 3
    assert target.read_bytes() == b'accepted original'
    target.unlink()
    assert render(source, target).returncode == 3
    assert not target.exists()


@pytest.mark.integration
def test_no_math_metadata_fails_strict_but_ordinary_documents_stay_compatible(tmp_path):
    source = samples(tmp_path)['math']
    target = tmp_path / 'math.pdf'
    assert render(source, target, '--no-metadata', '--verify-strict').returncode != 0
    assert not target.exists()
    ordinary = tmp_path / 'ordinary.md'
    ordinary.write_text('# Ordinary\n\nPlain CJK 普通正文.\n')
    assert render(ordinary, target, '--verify-strict').returncode == 0
    assert '/JZMathTotal' not in PdfReader(target).metadata


class _FormulaDOM(HTMLParser):
    def __init__(self):
        super().__init__()
        self.formulas = 0
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'katex' in attrs.get('class', '').split():
            self.formulas += 1
        self.scripts += tag == 'script'


@pytest.mark.integration
def test_math_html_is_rendered_offline_without_executable_scripts(tmp_path):
    source = samples(tmp_path)['math']
    target = tmp_path / 'math.html'
    result = render(source, target, '--format', 'html')
    assert result.returncode == 0, result.stderr
    dom = _FormulaDOM()
    dom.feed(target.read_text())
    assert dom.formulas == 4 and dom.scripts == 0


def test_setup_downloads_and_repairs_only_hash_verified_assets(tmp_path, monkeypatch):
    import io
    import json
    import urllib.request
    import math_rendering
    manifest = katex_manifest()
    payloads = {info['file'].removeprefix('katex/'): vendor_bytes(name, manifest)
                for name, info in manifest.items()}
    (tmp_path / 'vendor.lock.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(math_rendering, 'SCRIPTS', tmp_path)
    calls = []
    def download(url, timeout):
        calls.append(url)
        relative = url.split('/dist/', 1)[-1] if '/dist/' in url else 'LICENSE'
        return io.BytesIO(payloads[relative])
    monkeypatch.setattr(urllib.request, 'urlopen', download)
    assert math_rendering.ensure_katex_vendor()
    assert len(calls) == len(manifest)
    calls.clear()
    assert math_rendering.ensure_katex_vendor()
    assert not calls
    (tmp_path / manifest['katex']['file']).write_bytes(b'tampered')
    assert math_rendering.ensure_katex_vendor()
    assert len(calls) == 1
    assert math_rendering.vendor_bytes('katex') == payloads['katex.min.js']


@pytest.mark.integration
def test_heading_math_copies_in_toc_reconcile_once_per_source(tmp_path):
    source = tmp_path / 'toc.md'
    source.write_text('[TOC]\n\n# Equation $x^2$\n\nBody.\n')
    target = tmp_path / 'toc.pdf'
    result = render(source, target, '--verify-strict')
    assert result.returncode == 0, result.stderr
    meta = PdfReader(target).metadata
    assert meta['/JZMathTotal'] == meta['/JZMathRendered'] == '1'
