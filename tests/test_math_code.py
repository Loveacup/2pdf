"""Code protection follows Markdown block semantics before math extraction."""
from html.parser import HTMLParser

import markdown
import pytest

from code_spans import protect_code_spans, restore_code_spans
from math_rendering import extract_math, source_formula_count


def test_indented_code_dollars_are_not_math_and_source_roundtrips():
    source = '# Example\n\n    $x^2$\n'
    protected, store = protect_code_spans(source)
    assert restore_code_spans(protected, store) == source
    assert extract_math(protected)[1] == []
    assert source_formula_count(source) == 0


@pytest.mark.parametrize('source, expected', [
    ('\t$x$\n\n$real$', ['real']),
    ('    $x$\n\n    $$y$$\n\n$real$', ['real']),
    ('>     $x$\n>\n>     $$y$$\n\n$real$', ['real']),
    ('- Item\n\n        $x$\n\n    Continuation $real$.\n', ['real']),
    ('- Item\n\n    >     $x$\n\n$real$', ['real']),
    ('[^n]: Note\n\n        $x$\n\nRef [^n]. $real$', ['real']),
    ('    \\$x\\$ and $$y$$\n\n$real$', ['real']),
    ('    $first$\r\n\r\n\t$second$\r\n', []),
    ('Paragraph\n    $continuation$\n', ['continuation']),
    ('- Item\n\n    $paragraph$\n', ['paragraph']),
    ('- Item\n    - Child $child$\n', ['child']),
    ('`$single$` ``$double$ ` inside`` $real$', ['real']),
    ('`$multi\nline$` $real$', ['real']),
    ('~~~tex\n$x$\n~~~\n\n```tex\n$$y$$\n```\n\n$real$', ['real']),
])
def test_code_classification_matches_markdown_containers(source, expected):
    protected, store = protect_code_spans(source)
    assert restore_code_spans(protected, store) == source
    extracted, formulas = extract_math(protected)
    assert [formula['source'] for formula in formulas] == expected
    assert source_formula_count(source) == len(expected)
    restored = restore_code_spans(extracted, store)
    if not expected:
        assert restored == source


def test_no_math_keeps_existing_code_and_markdown_structure():
    from md2pdf_chrome import preprocess_markdown

    source = (
        '# Example\n\n'
        '- Parent\n\n'
        '        print("ordinary")\n\n'
        '>     quoted code\n\n'
        '```text\n==literal== [[target]]\n```\n\n'
        'Inline `==literal==`.\n'
    )
    protected, store = protect_code_spans(source)
    restored = restore_code_spans(preprocess_markdown(protected), store)
    assert restored == source
    extensions = ['fenced_code', 'sane_lists']
    assert markdown.markdown(restored, extensions=extensions) == markdown.markdown(
        source, extensions=extensions
    )


class _CodeDOM(HTMLParser):
    def __init__(self):
        super().__init__()
        self.code_depth = 0
        self.code = []
        self.math_nodes = 0

    def handle_starttag(self, tag, attrs):
        self.code_depth += tag == 'code'
        classes = dict(attrs).get('class', '').split()
        self.math_nodes += 'jz-math' in classes or 'katex' in classes

    def handle_endtag(self, tag):
        if tag == 'code':
            self.code_depth -= 1

    def handle_data(self, data):
        if self.code_depth:
            self.code.append(data)


@pytest.mark.integration
def test_build_html_keeps_indented_code_literal_and_renders_only_prose(tmp_path):
    from md2pdf_chrome import build_html

    source = tmp_path / 'code.md'
    source.write_text(
        '# Example\n\n    $x^2$\n\n'
        '>     $$quoted$$\n\n'
        '- Item\n\n        \\$escaped\\$\n\n'
        '$real$\n'
    )
    html = build_html(source, '', theme='blue')
    dom = _CodeDOM()
    dom.feed(html)
    assert dom.math_nodes == 1
    assert '$x^2$' in ''.join(dom.code)
    assert '$$quoted$$' in ''.join(dom.code)
    assert '\\$escaped\\$' in ''.join(dom.code)
    assert 'data-math-index="1"' in html
    assert 'data-math-index="2"' not in html


@pytest.mark.integration
def test_real_html_cli_does_not_render_indented_code_as_katex(tmp_path):
    from test_typesetting import render

    source = tmp_path / 'code.md'
    source.write_text('# Example\n\n    $x^2$\n')
    target = tmp_path / 'code.html'
    result = render(source, target, '--format', 'html')
    assert result.returncode == 0, result.stderr
    html = target.read_text()
    dom = _CodeDOM()
    dom.feed(html)
    assert dom.math_nodes == 0
    assert ''.join(dom.code).strip() == '$x^2$'
