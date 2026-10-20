"""Pandoc-dollar math recognition and a single pinned, offline KaTeX renderer."""
import base64
import hashlib
import json
import re
import secrets
from html import escape
from pathlib import Path

from resource_policy import ResourceError

KATEX_PIN = '0.16.22'
SCRIPTS = Path(__file__).resolve().parent


class MathRenderError(RuntimeError):
    """Formula content failure; never retry with another renderer."""


def _escaped(text, position):
    start = position
    while start and text[start - 1] == '\\':
        start -= 1
    return (position - start) % 2 == 1


def extract_math(text):
    """Input has code spans/fences protected. Unpaired dollars remain literal."""
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
    formulas, out, cursor, i = [], [], 0, 0
    nonce = secrets.token_hex(12)
    while i < len(text):
        # Dollars in markup attributes/destinations are not inline text.
        if text[i] == '<':
            raw = re.match(r'<!--.*?-->|<(script|style|pre|code)\b[^>]*>.*?</\1\s*>|</?[A-Za-z][^>]*>|<https?://[^>]*>', text[i:], re.S | re.I)
            if raw:
                i += raw.end()
                continue
        if text.startswith('](', i):
            depth, j = 1, i + 2
            while j < len(text) and depth:
                if not _escaped(text, j):
                    depth += (text[j] == '(') - (text[j] == ')')
                j += 1
            i = j
            continue
        if text[i] != '$' or _escaped(text, i):
            i += 1
            continue
        display = text.startswith('$$', i)
        size = 2 if display else 1
        start = i + size
        if not display and (start == len(text) or text[start].isspace()):
            i += 1
            continue
        end = start
        while True:
            end = text.find('$', end)
            if end < 0:
                break
            if _escaped(text, end):
                end += 1
                continue
            if display:
                if text.startswith('$$', end):
                    break
            elif not text.startswith('$$', end) and not text[end - 1].isspace() and not (end + 1 < len(text) and text[end + 1].isdigit()):
                break
            end += 2 if text.startswith('$$', end) else 1
        if end < 0 or not display and '\n\n' in text[start:end]:
            i += size
            continue
        ordinal = len(formulas) + 1
        token = f'JZMATH{nonce}TOKEN{ordinal}END'
        formulas.append({'index': ordinal, 'source': text[start:end], 'display': display, 'token': token})
        out.extend((text[cursor:i], token))
        i = cursor = end + size
    out.append(text[cursor:])
    plain = ''.join(out)
    plain = re.sub(r'(\\+)\$', lambda match: '\\' * (len(match[1]) - len(match[1]) % 2) + '$', plain)
    return plain, formulas


def restore_math_html(body, formulas):
    for formula in formulas:
        display = 'true' if formula['display'] else 'false'
        node = f'<span class="jz-math" data-math-index="{formula["index"]}" data-display="{display}">{escape(formula["source"])}</span>'
        body = body.replace(formula['token'], node)
    return body


def source_formula_count(source):
    # Use the existing fence-first contract rather than a second code parser.
    from code_spans import protect_code_spans
    protected, _ = protect_code_spans(source)
    return len(extract_math(protected)[1])


def katex_manifest():
    lock = json.loads((SCRIPTS / 'vendor.lock.json').read_text())
    entries = {key: info for key, info in lock.items() if key == 'katex' or key.startswith('katex-')}
    if not {'katex', 'katex-css', 'katex-license'} <= entries.keys() or not any(key.startswith('katex-font:') for key in entries):
        raise ResourceError('Incomplete pinned KaTeX vendor manifest')
    for info in entries.values():
        if info['version'] != KATEX_PIN or not info['file'].startswith('katex/') or '..' in Path(info['file']).parts:
            raise ResourceError('Invalid pinned KaTeX vendor entry')
    return entries


def vendor_bytes(name, manifest=None):
    info = (manifest or katex_manifest())[name]
    path = SCRIPTS / info['file']
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ResourceError(f'Offline KaTeX vendor missing: {path}; run maintenance.py init explicitly') from error
    if hashlib.sha256(data).hexdigest() != info['sha256']:
        raise ResourceError(f'KaTeX vendor hash mismatch: {path}; run explicit --setup to repair')
    return data


def _data_uri(mime, data):
    return f'data:{mime};base64,' + base64.b64encode(data).decode()


def math_assets(formulas):
    if not formulas:
        return ''
    manifest = katex_manifest()
    vendor_bytes('katex-license', manifest)
    css = vendor_bytes('katex-css', manifest).decode()
    # Keep only pinned WOFF2 sources, embed them without granting document roots.
    def font_source(match):
        filename = match[1]
        data = vendor_bytes('katex-font:' + Path(filename).stem, manifest)
        return 'src:url(' + _data_uri('font/woff2', data) + ') format("woff2")'
    css = re.sub(r'src:url\(fonts/([^)]*\.woff2)\)[^}]*', font_source, css)
    script = _data_uri('text/javascript', vendor_bytes('katex', manifest))
    return f'<link rel="stylesheet" href="{_data_uri("text/css", css.encode())}">\n<script src="{script}"></script>\n' + r'''<style>
.jz-math[data-display="true"] { display:block; break-inside:avoid; }
.jz-math .katex-display { margin:0.8em 0; }
</style><script>
window.__mathStatus = {total:0, rendered:0, errors:[], finished:false};
document.addEventListener('DOMContentLoaded', function() {
  const st = window.__mathStatus, nodes = Array.from(document.querySelectorAll('.jz-math'));
  st.total = new Set(nodes.map(node => node.dataset.mathIndex)).size;
  const rendered = new Set();
  for (const node of nodes) {
    const source = node.textContent;
    try {
      if (/\\(?:href|url|includegraphics|htmlClass|htmlId|htmlStyle|htmlData)\b/.test(source)) {
        throw new Error('Trust-dependent HTML/URL commands are not supported');
      }
      katex.render(source, node, {displayMode:node.dataset.display === 'true',
        trust:false, throwOnError:true, strict:'error', output:'htmlAndMathml'});
      rendered.add(node.dataset.mathIndex);
      st.rendered = rendered.size;
    } catch (error) {
      st.errors.push({index:Number(node.dataset.mathIndex), message:String(error.message || error), head:source.slice(0,160)});
    }
  }
  st.finished = true;
});
</script>'''


def math_check_js():
    return r'''
  const mathStatus = await page.evaluate(async () => {
    const st = window.__mathStatus;
    if (!st) return null;
    await document.fonts.ready;
    document.querySelectorAll('.jz-math').forEach(node => {
      const content = node.querySelector('.katex-html');
      if (!content) return;
      const rect = content.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.left < -1 || rect.right > document.documentElement.clientWidth + 1) {
        st.errors.push({index:Number(node.dataset.mathIndex), message:'Formula is invisible or exceeds page width', head:node.textContent.slice(0,160)});
      }
    });
    return st;
  });
  if (mathStatus) {
    console.log('MATH_STAT:' + JSON.stringify({total:mathStatus.total, rendered:mathStatus.rendered}));
    if (!mathStatus.finished || mathStatus.errors.length || mathStatus.total !== mathStatus.rendered) {
      console.error('MATH_ERRORS:' + JSON.stringify(mathStatus.errors));
      await browser.close(); process.exit(8);
    }
  }
'''


def format_math_errors(stderr):
    match = re.search(r'MATH_ERRORS:(.*)', stderr)
    errors = json.loads(match[1]) if match else []
    return '\n'.join(['Formula rendering failed; target unchanged:'] + [
        f'  Formula #{item["index"]}: {item["message"]}\n    TeX: {item["head"]}' for item in errors])


def ensure_katex_vendor(force=False):
    """Called only by explicit setup; verify every download before publishing it."""
    from urllib.request import urlopen
    ok = True
    for name, info in katex_manifest().items():
        try:
            if not force:
                try:
                    vendor_bytes(name)
                    continue
                except ResourceError:
                    pass
            relative = info['file'].removeprefix('katex/')
            suffix = 'LICENSE' if relative == 'LICENSE' else 'dist/' + relative
            url = f'https://cdn.jsdelivr.net/npm/katex@{KATEX_PIN}/{suffix}'
            with urlopen(url, timeout=30) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != info['sha256']:
                raise ResourceError(f'Hash mismatch downloading {name}')
            path = SCRIPTS / info['file']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except (OSError, ResourceError) as error:
            print(f'KaTeX setup failed for {name}: {error}')
            ok = False
    return ok
