"""WeChat exports retain offline math fonts and validate the delivered DOM."""
import json
import re

import css_inline
import pytest

import md2pdf_chrome
from test_typesetting import render


@pytest.mark.integration
def test_wechat_math_cli_preserves_embedded_fonts(tmp_path):
    source = tmp_path / 'math.md'
    source.write_text('# Formula\n\n$x^2 + \\frac{1}{2}$\n', encoding='utf-8')
    target = tmp_path / 'math.wechat.html'
    result = render(source, target, '--format', 'wechat')
    assert result.returncode == 0, result.stderr
    html = target.read_text(encoding='utf-8')
    assert html.count('@font-face') == 20
    assert 'data:font/woff2;base64,' in html
    assert re.search(r'<annotation\b[^>]*encoding="application/x-tex"', html)
    reports = [json.loads(line.partition('FONT_REPORT:')[2])
               for line in result.stderr.splitlines() if line.startswith('FONT_REPORT:')]
    assert len(reports) == 2, 'both pre-transform and delivered artifact need font validation'
    assert any(font['isCustomFont'] and 'KaTeX' in font['familyName']
               for font in reports[-1]['fonts'])
    assert reports[-1]['missing'] == reports[-1]['lastResort'] == []


def test_no_math_inlining_keeps_existing_structure():
    html = ('<html><head><style>@font-face{font-family:Plain;src:url(data:font/woff2;base64,AA==)}'
            'p{color:red}@media print{p{color:black}}</style>'
            '</head><body><p>ordinary</p></body></html>')
    assert md2pdf_chrome.inline_css(html) == css_inline.CSSInliner(
        load_remote_stylesheets=False).inline(html)


@pytest.mark.integration
@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('damage', ['resource', 'math'])
def test_wechat_validates_transformed_artifact_before_delivery(tmp_path, monkeypatch, existing, damage):
    source = tmp_path / 'math.md'
    source.write_text('$x^2$\n', encoding='utf-8')
    target = tmp_path / 'math.wechat.html'
    if existing:
        target.write_bytes(b'accepted original')
    original_inline = md2pdf_chrome.inline_css

    def damaged_inline(html):
        html = original_inline(html)
        if damage == 'resource':
            return html.replace('</body>', '<div style="background-image:url(https://example.invalid/blocked.png)">blocked</div></body>')
        return re.sub(r'(<span[^>]*class="[^"]*katex-html[^"]*"[^>]*style=")[^"]*',
                      r'\1display:none;', html)

    monkeypatch.setattr(md2pdf_chrome, 'inline_css', damaged_inline)
    error = md2pdf_chrome.ResourceError if damage == 'resource' else md2pdf_chrome.MathRenderError
    with pytest.raises(error):
        md2pdf_chrome.md_to_output(source, target, fmt='wechat')
    if existing:
        assert target.read_bytes() == b'accepted original'
    else:
        assert not target.exists()
