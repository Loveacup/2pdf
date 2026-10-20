"""Source-preserving code protection shared by both Markdown renderers."""
import re
import secrets


# Protect before Obsidian/image transformations: Mermaid ==> must remain literal.
_FENCE_RE = re.compile(r"^(?P<f>`{3,}|~{3,})[^\n]*\n(?:.*?\n)?(?P=f)[ \t]*$", re.M | re.S)
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)([^`\n]+?)\1(?!`)")


def _code_dollar_positions(md_text):
    """Let Markdown classify dollars without changing its block syntax."""
    if '$' not in md_text:
        return set()

    from markdown import Markdown
    from markdown.treeprocessors import Treeprocessor

    nonce = secrets.token_hex(12)
    prefix = f'JZCODEPROBE{nonce}TOKEN'
    token_re = re.compile(re.escape(prefix) + r'(\d+)END')
    positions = []
    code_positions = set()

    def probe(match):
        positions.append(match.start())
        return f'{prefix}{len(positions) - 1}END'

    class CollectCodeDollars(Treeprocessor):
        def run(self, root):
            for code in root.iter('code'):
                for match in token_re.finditer(''.join(code.itertext())):
                    code_positions.add(positions[int(match[1])])

    parser = Markdown(extensions=[
        'tables', 'fenced_code', 'toc', 'sane_lists', 'md_in_html', 'footnotes',
    ])
    parser.treeprocessors.register(CollectCodeDollars(parser), 'code_dollars', 0)
    parser.convert(re.sub(r'\$', probe, md_text))
    return code_positions


def protect_code_spans(md_text):
    """Hide code from transformations, preserving exact source on restoration.

    Fences and inline spans retain their existing whole-span protection.
    Indented code uses Markdown's own parser to shield its dollars; retaining
    its whitespace and container prefixes avoids changing list/quote structure.
    """
    regions = [match.span() for match in _FENCE_RE.finditer(md_text)]
    for match in _INLINE_CODE_RE.finditer(md_text):
        if not any(start <= match.start() < end for start, end in regions):
            regions.append(match.span())
    for position in _code_dollar_positions(md_text):
        if not any(start <= position < end for start, end in regions):
            regions.append((position, position + 1))

    store, output, cursor = [], [], 0
    for start, end in sorted(regions):
        output.append(md_text[cursor:start])
        output.append(f"\x02JZCODE{len(store)}\x03")
        store.append(md_text[start:end])
        cursor = end
    output.append(md_text[cursor:])
    return ''.join(output), store


def restore_code_spans(md_text, store):
    for i, block in enumerate(store):
        md_text = md_text.replace(f"\x02JZCODE{i}\x03", block)
    return md_text
