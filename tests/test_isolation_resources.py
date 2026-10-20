"""P0-B behavior contracts. Integration exercises real CLI processes and loopback counts."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import quote

import pytest
import md2pdf_chrome as m
from pdf_delivery import DeliveryError, staged_output, target_ownership
from resource_policy import ResourcePolicy, ResourceError, seal_html
from test_content_preservation import bitmap_bytes

SCRIPT = str(Path(m.__file__).resolve())
FORMATS = ('pdf', 'png', 'html', 'wechat')


def command(source, target, fmt, *flags):
    return [sys.executable, SCRIPT, str(source), str(target), '--format', fmt,
            '--browser', 'auto', '--theme', 'blue', *flags]


def cli(source, target, fmt, *flags):
    cmd = command(source, target, fmt, *flags)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    evidence = os.environ.get('JZ2PDF_EVIDENCE_DIR')
    if evidence:
        folder = Path(evidence)
        folder.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256((' '.join(cmd) + str(time.time_ns())).encode()).hexdigest()[:16]
        (folder / (key + '.json')).write_text(json.dumps({'command': cmd, 'returncode': result.returncode,
                                                        'stdout': result.stdout, 'stderr': result.stderr}, ensure_ascii=False, indent=2))
    return result


def artifact_text(target, fmt):
    if fmt == 'pdf':
        from pypdf import PdfReader
        return '\n'.join(page.extract_text() or '' for page in PdfReader(target).pages)
    if fmt == 'png':
        result = subprocess.run(['tesseract', str(target), 'stdout', '--psm', '6'],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        return result.stdout
    return target.read_text()


@contextmanager
def counting_server():
    counts, requests = {}, []
    entered, release = threading.Event(), threading.Event()
    state = {'redirect': None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            counts[self.path] = counts.get(self.path, 0) + 1
            requests.append(dict(self.headers))
            if self.path == '/hold':
                entered.set()
                release.wait(40)
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', state['redirect'])
                self.end_headers()
                return
            if self.path == '/style.css':
                data, mime = b'p { background: url(/image.png); }', 'text/css'
            elif self.path == '/nested.svg':
                data, mime = b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><image href="/image.png" width="32" height="32"/></svg>', 'image/svg+xml'
            else:
                data, mime = bitmap_bytes(), 'image/png'
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', counts, requests, entered, release, state
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join()
        evidence = os.environ.get('JZ2PDF_EVIDENCE_DIR')
        if evidence:
            folder = Path(evidence)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f'server-{server.server_port}-{time.time_ns()}.json').write_text(
                json.dumps({'origin': f'http://127.0.0.1:{server.server_port}',
                            'counts': counts, 'request_headers': requests}, indent=2))


def test_cli_repeatable_policy_arguments():
    args = m.parse_cli_args(['in.md', '--resource-root', 'one', '--resource-root', 'two',
                             '--allow-origin', 'https://one.test', '--allow-origin', 'https://two.test'])
    assert args['resource_roots'] == ['one', 'two']
    assert args['allowed_origins'] == ['https://one.test', 'https://two.test']
    for flag in ('--resource-root', '--allow-origin'):
        with pytest.raises(ValueError):
            m.parse_cli_args(['in.md', flag])


def test_normalized_target_lock_and_exception_cleanup(tmp_path):
    target = tmp_path / 'out.html'
    target.write_text('previous')
    with target_ownership(target):
        with pytest.raises(DeliveryError):
            with target_ownership(tmp_path / 'child' / '..' / target.name):
                pytest.fail('second owner')
        with target_ownership(tmp_path / 'other.html'):
            pass
    with pytest.raises(RuntimeError):
        with staged_output(target, tmp_path / 'in.md', 'html') as stage:
            stage.write_text('<html>not delivered</html>')
            raise RuntimeError('injected failure')
    assert target.read_text() == 'previous'
    assert not list(tmp_path.glob('.2pdf-stage-*'))
    with staged_output(target, tmp_path / 'in.md', 'html') as stage:
        stage.write_text('<html>accepted</html>')
    assert target.read_text() == '<html>accepted</html>'


def test_process_exit_releases_output_ownership(tmp_path):
    target = tmp_path / 'out.html'
    code = ('import sys,time; sys.path.insert(0, sys.argv[1]); '
            'from pdf_delivery import target_ownership; '
            'owner=target_ownership(sys.argv[2]); owner.__enter__(); '
            'print("owned", flush=True); time.sleep(60)')
    proc = subprocess.Popen([sys.executable, '-c', code, str(Path(SCRIPT).parent), str(target)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == 'owned'
        with pytest.raises(DeliveryError):
            with target_ownership(target):
                pytest.fail('second process owner')
    finally:
        proc.kill()
        proc.communicate(timeout=10)
    with target_ownership(target):
        pass


@pytest.mark.parametrize('reference', ['../outside.png', '%2e%2e/outside.png', 'escape.png'])
def test_real_root_escape_rejected(tmp_path, reference):
    source = tmp_path / 'source'
    source.mkdir()
    outside = tmp_path / 'outside.png'
    outside.write_bytes(bitmap_bytes())
    (source / 'escape.png').symlink_to(outside)
    policy = ResourcePolicy(source / 'in.md')
    with pytest.raises(ResourceError):
        policy.resource(reference)
    with pytest.raises(ResourceError):
        policy.resource(str(outside))
    assert base64.b64encode(outside.read_bytes()).decode() in ResourcePolicy(source / 'in.md', [tmp_path]).resource(reference)


@pytest.mark.parametrize('markup', [
    '<img src="{origin}/image.png">', '<link rel="stylesheet" href="{origin}/style.css">',
    '<style>@import "{origin}/style.css";</style>', '<p style="background: u\\72l({origin}/image.png)">x</p>',
    '<style>@font-face {{font-family: test; src: url({origin}/font.woff)}}</style>',
    '<svg><image href="{origin}/image.png"/></svg>', '<iframe src="{origin}/frame"></iframe>',
    '<script src="{origin}/script.js"></script>',
])
def test_offline_resource_types_fail_before_network(tmp_path, markup):
    with counting_server() as (origin, counts, *_):
        with pytest.raises(ResourceError):
            ResourcePolicy(tmp_path / 'in.md').html(markup.format(origin=origin))
        assert counts == {}


def test_svg_indirect_access_and_case_preservation(tmp_path):
    path = tmp_path / 'local.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="red"/></svg>')
    frozen = ResourcePolicy(tmp_path / 'in.md').resource(path.name)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(base64.b64decode(frozen.split(',', 1)[1]))
    assert root.attrib['viewBox'] == '0 0 32 32'
    with counting_server() as (origin, counts, *_):
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg"><image href="{origin}/image.png"/></svg>')
        with pytest.raises(ResourceError):
            ResourcePolicy(tmp_path / 'in.md').resource(path.name)
        assert counts == {}


def test_missing_vendor_never_fetches(monkeypatch, tmp_path):
    monkeypatch.setattr(m, 'MERMAID_LOCAL', tmp_path / 'missing.js')
    with pytest.raises(ResourceError):
        m.get_mermaid_src()
    monkeypatch.setattr(m, 'HLJS_LOCAL', tmp_path / 'missing.js')
    with pytest.raises(ResourceError):
        m._hljs_js_src()


@pytest.mark.integration
@pytest.mark.parametrize('fmt', FORMATS)
def test_ten_concurrent_same_stem_outputs(tmp_path, fmt):
    sentinels = ['SENTINEL' + word for word in
                 ('ALPHA', 'BRAVO', 'CHARLIE', 'DELTA', 'ECHO', 'FOXTROT', 'GOLF', 'HOTEL', 'INDIA', 'JULIET')]
    def render(index):
        folder = tmp_path / str(index)
        folder.mkdir()
        source, target = folder / 'same.md', folder / ('out.' + ('html' if fmt == 'wechat' else fmt))
        source.write_text(f'<h1 style="font-size:48px">{sentinels[index]}</h1>\n\nOwn content {index}')
        result = cli(source, target, fmt)
        assert result.returncode == 0, result.stdout + result.stderr
        text = artifact_text(target, fmt)
        assert sentinels[index] in text, text
        assert all(other not in text for other in sentinels if other != sentinels[index])
        assert not list(folder.glob('.2pdf-stage-*'))
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(render, range(10)))


@pytest.mark.integration
@pytest.mark.parametrize('fmt', FORMATS)
def test_same_target_conflict_cancel_exception_and_sequential_overwrite(tmp_path, fmt):
    source, target = tmp_path / 'same.md', tmp_path / ('out.' + fmt)
    target.write_bytes(b'prior accepted artifact')
    companion = tmp_path / 'companion.md'
    companion.write_text('# COMPANION SENTINEL')
    companion_target = tmp_path / 'companion.html'
    with counting_server() as (origin, counts, requests, entered, release, _):
        source.write_text(f'# OWNER\n\n![held]({origin}/hold)')
        cmd = command(source, target, fmt, '--allow-origin', origin)
        first = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        other = subprocess.Popen(command(companion, companion_target, 'html'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert entered.wait(30)
            before = time.monotonic()
            conflict = cli(source, target, fmt, '--allow-origin', origin)
            assert conflict.returncode != 0
            assert time.monotonic() - before < 5
            assert target.read_bytes() == b'prior accepted artifact'
            first.send_signal(signal.SIGTERM)
            stdout, stderr = first.communicate(timeout=20)
            assert first.returncode == 130, stdout + stderr
            release.set()
            out, err = other.communicate(timeout=120)
            assert other.returncode == 0, out + err
            assert 'COMPANION SENTINEL' in companion_target.read_text()
            assert target.read_bytes() == b'prior accepted artifact'
            assert not list(tmp_path.glob('.2pdf-stage-*'))
        finally:
            release.set()
            for proc in (first, other):
                if proc.poll() is None:
                    proc.terminate()
                    proc.communicate(timeout=20)
    source.write_text('# REPLACEMENT SENTINEL')
    success = cli(source, target, fmt)
    assert success.returncode == 0, success.stdout + success.stderr
    accepted = target.read_bytes()
    source.write_text('![bad](invalid.svg)')
    (tmp_path / 'invalid.svg').write_text('<svg broken')
    failed = cli(source, target, fmt)
    assert failed.returncode != 0
    assert target.read_bytes() == accepted
    assert not list(tmp_path.glob('.2pdf-stage-*'))


@pytest.mark.integration
@pytest.mark.parametrize('fmt', FORMATS)
def test_real_cli_roots_unicode_and_escape(tmp_path, fmt):
    source_dir, assets = tmp_path / 'source', tmp_path / '授权 assets'
    source_dir.mkdir()
    assets.mkdir()
    image = assets / '图 像.png'
    image.write_bytes(bitmap_bytes())
    secret = assets / 'outside.html'
    secret.write_text('<h1>OUTSIDE_SECRET_SENTINEL</h1>')
    (source_dir / 'escape.html').symlink_to(secret)
    source, target = source_dir / 'same.md', tmp_path / ('out.' + fmt)
    source.write_text(f'# OWN_SENTINEL\n\n![image](../{quote(assets.name)}/{quote(image.name)})')
    success = cli(source, target, fmt, '--resource-root', str(assets))
    assert success.returncode == 0, success.stdout + success.stderr
    accepted = target.read_bytes()
    assert 'OUTSIDE_SECRET_SENTINEL' not in artifact_text(target, fmt)
    for reference in ('../' + quote(assets.name) + '/outside.html', str(secret), 'escape.html'):
        source.write_text(f'<iframe src="{reference}"></iframe>')
        failed = cli(source, target, fmt)
        assert failed.returncode != 0
        assert target.read_bytes() == accepted


@pytest.mark.integration
@pytest.mark.parametrize('fmt', FORMATS)
def test_real_offline_zero_requests_and_document_scripts_inert(tmp_path, fmt):
    source, target = tmp_path / 'same.md', tmp_path / ('out.' + fmt)
    with counting_server() as (origin, counts, *_):
        (tmp_path / 'indirect.css').write_text(f'body {{ background: url({origin}/css-image); }}')
        (tmp_path / 'indirect.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg"><image href="{origin}/svg-image"/></svg>')
        cases = [f'<img src="{origin}/image.png">', '<link rel="stylesheet" href="indirect.css">',
                 '![svg](indirect.svg)', f'<iframe src="{origin}/frame"></iframe>',
                 f'<script src="{origin}/script.js"></script>',
                 f'<style>@font-face {{font-family:x; src:url({origin}/font)}}</style>']
        for markup in cases:
            source.write_text('# OFFLINE\n\n' + markup)
            result = cli(source, target, fmt)
            assert result.returncode != 0, markup
            assert not target.exists()
        source.write_text(f'''# INERT_SCRIPT_SENTINEL
<script>fetch('{origin}/fetch'); new Image().src='{origin}/script-image'; document.body.innerHTML='SCRIPT_EXECUTED';</script>
<img src="data:image/png;base64,{base64.b64encode(bitmap_bytes()).decode()}" onload="fetch('{origin}/onload')">
''')
        result = cli(source, target, fmt)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'SCRIPT_EXECUTED' not in artifact_text(target, fmt)
        assert counts == {}
        # Direct browser-level defense, without Python preprocessing: CSP violation
        # plus interception must fail the artifact with zero loopback requests.
        html = tmp_path / 'untrusted.html'
        html.write_text(seal_html(f'<html><head></head><body style="background:url({origin}/bypass)">blocked</body></html>'))
        with pytest.raises(ResourceError):
            if fmt == 'pdf':
                m._render_playwright(html, tmp_path / 'blocked.pdf', browser='auto')
            else:
                m._render_playwright_output(html, tmp_path / ('blocked.' + fmt), fmt, browser='auto')
        assert counts == {}


@pytest.mark.integration
@pytest.mark.parametrize('fmt', FORMATS)
def test_explicit_origins_redirects_and_request_counts(tmp_path, fmt):
    source, target = tmp_path / 'same.md', tmp_path / ('out.' + fmt)
    with counting_server() as (allowed, counts, requests, _, __, state), counting_server() as (denied, denied_counts, *_):
        source.write_text(f'# REMOTE SENTINEL\n\n![allowed]({allowed}/image.png)\n\n<link rel="stylesheet" href="{allowed}/style.css">\n\n![nested]({allowed}/nested.svg)')
        result = cli(source, target, fmt, '--allow-origin', allowed)
        assert result.returncode == 0, result.stdout + result.stderr
        assert counts == {'/image.png': 1, '/style.css': 1, '/nested.svg': 1}
        assert all('Cookie' not in item and 'Authorization' not in item for item in requests)
        accepted = target.read_bytes()
        source.write_text(f'![denied]({denied}/image.png)')
        result = cli(source, target, fmt, '--allow-origin', allowed)
        assert result.returncode != 0
        assert denied_counts == {}
        assert target.read_bytes() == accepted
        state['redirect'] = denied + '/image.png'
        source.write_text(f'![redirect]({allowed}/redirect)')
        result = cli(source, target, fmt, '--allow-origin', allowed)
        assert result.returncode != 0
        assert counts['/redirect'] == 1
        assert denied_counts == {}
        assert target.read_bytes() == accepted
        state['redirect'] = allowed + '/image.png'
        result = cli(source, target, fmt, '--allow-origin', allowed)
        assert result.returncode == 0, result.stdout + result.stderr
        assert counts['/redirect'] == 2 and counts['/image.png'] == 2


@pytest.mark.integration
def test_existing_sample_verify_and_setup_smoke_offline(tmp_path, monkeypatch):
    source = Path(SCRIPT).parent.parent / 'tests/fixtures/sample.md'
    result = cli(source, tmp_path / 'sample.pdf', 'pdf', '--verify')
    assert result.returncode == 0, result.stdout + result.stderr
    # Exercise run_setup's actual smoke subprocess while explicitly skipping only
    # provisioning: no downloads, environment changes, or second browser install.
    monkeypatch.setattr(m, '_bootstrap_venv', lambda: Path(sys.executable))
    monkeypatch.setattr(m, '_bundled_launchable', lambda: True)
    monkeypatch.setattr(m, '_ensure_vendor', lambda: True)
    assert m.run_setup() == 0


@pytest.mark.integration
def test_pandoc_fallback_refuses_instead_of_bypassing(tmp_path):
    source, target = tmp_path / 'in.md', tmp_path / 'out.pdf'
    source.write_text('# SAFE')
    target.write_bytes(b'previous')
    result = cli(source, target, 'pdf', '--fallback', 'pandoc')
    assert result.returncode != 0
    assert target.read_bytes() == b'previous'
