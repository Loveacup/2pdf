"""Document resources are authorized, recursively frozen, and never fetched by Chromium."""
import base64
import mimetypes
import re
import secrets
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, unquote_to_bytes, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class ResourceError(ValueError):
    """A document resource violates its invocation's access policy."""


def origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ResourceError(f'Invalid HTTP(S) origin: {url!r}')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    return (parsed.scheme.lower(), parsed.hostname.lower(), port)


class ResourcePolicy:
    def __init__(self, source, extra_roots=(), allowed_origins=()):
        self.base = Path(source).resolve().parent.as_uri() + '/'
        self.roots = [Path(source).resolve().parent]
        for root in extra_roots:
            path = Path(root).resolve(strict=True)
            if not path.is_dir():
                raise ResourceError(f'Resource root is not a directory: {root}')
            self.roots.append(path)
        self.origins = set()
        for item in allowed_origins:
            parsed = urlsplit(item)
            if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                raise ResourceError(f'Use an origin, not a resource URL: {item!r}')
            self.origins.add(origin(item))
        self.active = set()
        self.cache = {}

    def authorize(self, reference, base=None):
        reference = reference.strip()
        url = urljoin(base or self.base, reference)
        parsed = urlsplit(url)
        if parsed.scheme in ('http', 'https'):
            if origin(url) not in self.origins:
                raise ResourceError(f'Remote resource {reference!r} is blocked (offline by default). '
                                    'Copy it beneath the source directory or explicitly authorize its origin with --allow-origin ORIGIN.')
        elif parsed.scheme == 'file':
            if parsed.netloc not in ('', 'localhost'):
                raise ResourceError(f'Nonlocal file resource blocked: {reference!r}')
            path = Path(unquote(parsed.path)).resolve()
            if not any(path.is_relative_to(root) for root in self.roots):
                raise ResourceError(f'Resource {reference!r} escapes authorized roots; use --resource-root DIR to grant access.')
        elif parsed.scheme != 'data':
            raise ResourceError(f'Unsupported resource URL: {reference!r}')
        return url

    def resource(self, reference, base=None):
        if reference.startswith('#'):
            return reference
        url = self.authorize(reference, base)
        if url in self.cache:
            return self.cache[url]
        if url in self.active:
            raise ResourceError(f'Cyclic resource reference: {reference!r}')
        self.active.add(url)
        try:
            parsed = urlsplit(url)
            if parsed.scheme == 'data':
                header, payload = url.split(',', 1)
                mime = (header[5:].split(';')[0] or 'text/plain').lower()
                data = base64.b64decode(payload) if ';base64' in header.lower() else unquote_to_bytes(payload)
                resource_base = base or self.base
            elif parsed.scheme == 'file':
                path = Path(unquote(parsed.path)).resolve()
                try:
                    data = path.read_bytes()
                except OSError as exc:
                    raise ResourceError(f'Resource {reference!r}: {exc}') from exc
                mime = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
                resource_base = url
            else:
                policy = self

                class Redirects(HTTPRedirectHandler):
                    def redirect_request(self, request, fp, code, msg, headers, newurl):
                        policy.authorize(newurl)
                        return super().redirect_request(request, fp, code, msg, headers, newurl)

                # No proxy environment, cookie jar, profile, netrc or inherited credentials.
                opener = build_opener(ProxyHandler({}), Redirects())
                try:
                    with opener.open(Request(url, headers={'User-Agent': '2pdf-resource-loader'}), timeout=30) as response:
                        self.authorize(response.url)
                        data = response.read()
                        mime = response.headers.get_content_type()
                        resource_base = response.url
                except ResourceError:
                    raise
                except Exception as exc:
                    raise ResourceError(f'Resource {reference!r}: {exc}') from exc
            if mime == 'text/css':
                data = self.css(data.decode('utf-8-sig'), resource_base).encode()
            elif mime == 'image/svg+xml':
                data = self.svg(data.decode('utf-8-sig'), resource_base).encode()
            elif mime in ('text/html', 'application/xhtml+xml'):
                data = self.html(data.decode('utf-8-sig'), resource_base).encode()
            uri = f'data:{mime};base64,{base64.b64encode(data).decode()}'
            self.cache[url] = uri
            return uri
        finally:
            self.active.remove(url)

    def css(self, text, base=None):
        # Decode CSS escapes before identifying URLs; Chromium's CSP remains a second boundary.
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        text = re.sub(r'\\([0-9a-fA-F]{1,6})\s?|\\([^\r\n])',
                      lambda m: chr(int(m[1], 16)) if m[1] else m[2], text)
        text = re.sub(r'@import\s+[\'"]([^\'"]+)[\'"]',
                      lambda m: '@import url("' + self.resource(m[1], base) + '")', text, flags=re.I)
        return re.sub(r'url\(\s*(?:"([^"]*)"|\'([^\']*)\'|([^)]*))\s*\)',
                      lambda m: 'url("' + self.resource(next(x for x in m.groups() if x is not None).strip(), base) + '")',
                      text, flags=re.I)

    def html(self, text, base=None):
        parser = _Document(self, base or self.base)
        parser.feed(text)
        parser.close()
        return ''.join(parser.out)

    def svg(self, text, base=None):
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ResourceError(f'Invalid SVG resource: {exc}') from exc
        for element in root.iter():
            for child in list(element):
                if child.tag.rsplit('}', 1)[-1].lower() in ('script', 'foreignObject'.lower()):
                    if child.attrib.get('src'):
                        self.authorize(child.attrib['src'], base)
                    element.remove(child)
            for key, value in list(element.attrib.items()):
                name = key.rsplit('}', 1)[-1].lower()
                if name.startswith('on'):
                    del element.attrib[key]
                elif name == 'style' or re.search(r'url\s*\(', value, re.I):
                    element.attrib[key] = self.css(value, base)
                elif name in ('href', 'src'):
                    element.attrib[key] = self.resource(value, base)
            if element.tag.rsplit('}', 1)[-1] == 'style' and element.text:
                element.text = self.css(element.text, base)
        return ET.tostring(root, encoding='unicode')


class _Document(HTMLParser):
    def __init__(self, policy, base):
        super().__init__(convert_charrefs=True)
        self.policy, self.base, self.out = policy, base, []
        self.skip = 0
        self.style = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.skip:
            if tag == 'script':
                self.skip += 1
            return
        if tag == 'script':
            if attrs.get('src'):
                self.policy.authorize(attrs['src'], self.base)
            self.skip = 1
            return
        if tag in ('base', 'meta', 'object', 'embed'):
            for key in ('src', 'data'):
                if attrs.get(key):
                    self.policy.authorize(attrs[key], self.base)
            return
        clean = []
        for key, value in attrs.items():
            if key.startswith('on') or key in ('nonce', 'integrity', 'crossorigin', 'ping', 'formaction', 'action', 'data-jz-local-source'):
                continue
            if value is None:
                clean.append(key)
                continue
            if key == 'style' or re.search(r'url\s*\(', value, re.I):
                value = self.policy.css(value, self.base)
            elif key == 'srcdoc':
                value = self.policy.html(value, self.base)
            elif key == 'srcset':
                # Freeze each candidate. Data URIs already work in src and avoid ambiguous comma parsing.
                if value.lstrip().startswith('data:'):
                    raise ResourceError('Use src rather than a data-URI srcset')
                candidates = []
                for candidate in value.split(','):
                    parts = candidate.strip().split()
                    if parts:
                        candidates.append(' '.join([self.policy.resource(parts[0], self.base)] + parts[1:]))
                value = ', '.join(candidates)
            elif key in ('src', 'poster', 'background') or (key in ('href', 'xlink:href') and tag not in ('a', 'area')):
                value = self.policy.resource(value, self.base)
                if tag == 'img':
                    source = attrs.get('data-jz-local-source', attrs.get(key, ''))
                    clean.append('data-jz-local-source="' + escape(source, quote=True) + '"')
            elif key in ('href', 'xlink:href') and urlsplit(value).scheme.lower() not in ('', 'http', 'https', 'mailto'):
                continue
            clean.append(f'{key}="{escape(value, quote=True)}"')
        self.out.append('<' + tag + (' ' + ' '.join(clean) if clean else '') + '>')
        self.style = tag == 'style'

    def handle_startendtag(self, tag, attrs):
        previous = len(self.out)
        self.handle_starttag(tag, attrs)
        if len(self.out) > previous:
            self.out[-1] = self.out[-1][:-1] + '/>'

    def handle_endtag(self, tag):
        if self.skip:
            if tag == 'script':
                self.skip -= 1
            return
        if tag not in ('base', 'meta', 'object', 'embed'):
            self.out.append(f'</{tag}>')
        self.style = False

    def handle_data(self, data):
        if not self.skip:
            self.out.append(self.policy.css(data, self.base) if self.style else escape(data, quote=False))


def vendor_uri(path):
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ResourceError(f'Offline vendor missing/unreadable: {path}; run maintenance.py init explicitly.') from exc
    mime = 'text/javascript' if path.suffix == '.js' else 'text/css'
    return f'data:{mime};base64,{base64.b64encode(data).decode()}'


def seal_html(html):
    """Only renderer-authored scripts remain at this boundary."""
    nonce = secrets.token_hex(24)
    html = re.sub(r'<script\b', f'<script nonce="{nonce}"', html)
    csp = ("default-src 'none'; img-src data: blob:; style-src 'unsafe-inline' data:; "
           f"script-src 'nonce-{nonce}'; font-src data:; frame-src data:; "
           "connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
    return html.replace('<head>', '<head>\n<meta http-equiv="Content-Security-Policy" content="' + csp + '">', 1)


def browser_policy_js(html_path):
    import json
    return """
  const context = await browser.newContext({ serviceWorkers: 'block' });
  const blockedResources = [];
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (url === __HTML_URL__ || url.startsWith('data:') || url === 'about:blank') {
      await route.continue();
    } else {
      blockedResources.push(url);
      await route.abort('blockedbyclient');
    }
  });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__resourceViolations = [];
    document.addEventListener('securitypolicyviolation', event => {
      window.__resourceViolations.push(event.blockedURI + ' [' + event.violatedDirective + ']');
    });
  });
""".replace('__HTML_URL__', json.dumps(Path(html_path).resolve().as_uri()))


def browser_resource_check_js():
    return """
  const violations = await page.evaluate(() => window.__resourceViolations || []);
  if (blockedResources.length || violations.length) {
    console.error('RESOURCE_POLICY:' + JSON.stringify([...blockedResources, ...violations]));
    await browser.close();
    process.exit(5);
  }
"""
