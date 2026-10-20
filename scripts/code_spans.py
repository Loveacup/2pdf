"""Fence-first protection shared by both Markdown renderers."""
import re


# Protect before Obsidian/image transformations: Mermaid ==> must remain literal.
_FENCE_RE = re.compile(r"^(?P<f>`{3,}|~{3,})[^\n]*\n(?:.*?\n)?(?P=f)[ \t]*$", re.M | re.S)
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)([^`\n]+?)\1(?!`)")


def protect_code_spans(md_text):
    """Extract fenced and inline code, returning (protected text, stored spans)."""
    store = []

    def _stash(match):
        store.append(match.group(0))
        return f"\x02JZCODE{len(store) - 1}\x03"

    md_text = _FENCE_RE.sub(_stash, md_text)
    md_text = _INLINE_CODE_RE.sub(_stash, md_text)
    return md_text, store


def restore_code_spans(md_text, store):
    for i, block in enumerate(store):
        md_text = md_text.replace(f"\x02JZCODE{i}\x03", block)
    return md_text
