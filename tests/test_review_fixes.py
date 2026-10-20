"""Behavior regressions from the independent P0 review."""
import nturl2path
from pathlib import Path, PureWindowsPath
import json
import subprocess
import sys

import pytest
import md2pdf_chrome as main
import md2pdf_browser as legacy

import resource_policy
from test_content_preservation import bitmap_bytes


def test_windows_file_url_decodes_to_absolute_authorized_path(monkeypatch):
    monkeypatch.setattr(resource_policy, 'url2pathname', nturl2path.url2pathname)
    path = PureWindowsPath(resource_policy.file_url_path('file:///C:/notes/space%20%23%20%E4%B8%AD.png'))
    assert path == PureWindowsPath(r'C:\notes\space # 中.png')
    assert path.is_absolute()
    assert path.is_relative_to(PureWindowsPath(r'C:\notes'))


def write_view_svg(tmp_path):
    (tmp_path / 'view.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
        '<rect width="40" height="40" fill="red"/>'
        '<rect x="40" width="40" height="40" fill="blue"/></svg>')


def test_frozen_svg_preserves_view_fragment_and_shares_payload(tmp_path):
    write_view_svg(tmp_path)
    policy = resource_policy.ResourcePolicy(tmp_path / 'in.md')
    full = policy.resource('view.svg')
    assert policy.resource('view.svg#svgView(viewBox(40,0,40,40))') == full + '#svgView(viewBox(40,0,40,40))'


@pytest.mark.parametrize('nested', [False, True])
def test_external_svg_use_fails_explicitly_with_source(tmp_path, nested):
    (tmp_path / 'sprite.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><symbol id="square">'
        '<rect width="40" height="40"/></symbol></svg>')
    markup = '<svg xmlns="http://www.w3.org/2000/svg"><use href="sprite.svg#square"/></svg>'
    policy = resource_policy.ResourcePolicy(tmp_path / 'in.md')
    with pytest.raises(resource_policy.ResourceError, match=r'External SVG.*sprite\.svg#square'):
        if nested:
            (tmp_path / 'nested.svg').write_text(markup)
            policy.resource('nested.svg')
        else:
            policy.html(markup)
    assert '<use href="#square"' in policy.html('<svg><use href="#square"/></svg>')


@pytest.mark.integration
def test_real_cli_svg_view_renders_selected_blue_region(tmp_path):
    write_view_svg(tmp_path)
    source, target = tmp_path / 'view.md', tmp_path / 'view.html'
    source.write_text('<img src="view.svg#svgView(viewBox(40,0,40,40))">')
    result = subprocess.run(
        [sys.executable, main.__file__, str(source), str(target), '--format', 'html', '--theme', 'blue'],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    script = """
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(process.argv[1]);
  const pixel = await page.evaluate(async () => {
    const image = document.querySelector('img');
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 40;
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0, 40, 40);
    return Array.from(context.getImageData(10, 10, 1, 1).data);
  });
  console.log(JSON.stringify(pixel));
  await browser.close();
})();
"""
    probe = subprocess.run(['node', '-e', script, target.as_uri()], env=main._node_env(),
                           capture_output=True, text=True, timeout=60)
    assert probe.returncode == 0, probe.stderr
    assert json.loads(probe.stdout) == [0, 0, 255, 255]


@pytest.mark.integration
@pytest.mark.parametrize('corrupt', [False, True], ids=['missing', 'corrupt'])
@pytest.mark.parametrize('markup', [
    '<img srcset="bad.png 1x">',
    '<img srcset="good.png 1x, bad.png 2x">',
    '<img srcset="bad.png 0.1x, good.png 1x">',
    '<picture><source srcset="good.png 1x, bad.png 2x"><img src="good.png"></picture>',
])
def test_srcset_candidates_fail_with_original_source(tmp_path, markup, corrupt):
    (tmp_path / 'good.png').write_bytes(bitmap_bytes())
    if corrupt:
        (tmp_path / 'bad.png').write_bytes(b'not an image')
    source, target = tmp_path / 'srcset.md', tmp_path / 'srcset.html'
    source.write_text(markup)
    target.write_text('previous accepted artifact')
    result = subprocess.run(
        [sys.executable, main.__file__, str(source), str(target), '--format', 'html', '--theme', 'blue'],
        capture_output=True, text=True, timeout=120)
    assert result.returncode != 0
    assert 'bad.png' in result.stdout + result.stderr
    assert target.read_text() == 'previous accepted artifact'


def test_legacy_fence_first_preserves_literal_images_and_obsidian_syntax(tmp_path):
    source = tmp_path / 'code.md'
    source.write_text('# LEGACY_SENTINEL\n\n```markdown\n![example](missing.png)\n'
                      '[[literal]] ==literal==\n```\n\n`![inline](missing-inline.png)`')
    html = legacy.build_html(source, 'LEGACY_HEADER')
    assert '![example](missing.png)' in html
    assert '[[literal]] ==literal==' in html
    assert '<code>![inline](missing-inline.png)</code>' in html
    assert '<img' not in html


@pytest.mark.integration
def test_legacy_cli_code_image_literals_render_as_text(tmp_path):
    source, target = tmp_path / 'code.md', tmp_path / 'code.pdf'
    source.write_text('# LEGACY_SENTINEL\n\n```markdown\n![example](missing.png)\n```\n\n'
                      '`![inline](missing-inline.png)`')
    result = subprocess.run(
        [sys.executable, legacy.__file__, str(source), str(target), 'LEGACY_HEADER',
         '--verify', '--require-text', 'LEGACY_SENTINEL'],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    from pypdf import PdfReader
    text = ''.join(page.extract_text() for page in PdfReader(target).pages)
    assert '![example](missing.png)' in text
    assert '![inline](missing-inline.png)' in text


@pytest.mark.integration
@pytest.mark.parametrize('directory', [
    'out # quoted',
    pytest.param("out ? % ' 中", marks=pytest.mark.skipif(sys.platform == 'win32', reason='? is not a Windows filename')),
])
def test_legacy_cli_output_directory_is_a_file_uri(tmp_path, directory):
    source, target = tmp_path / 'plain.md', tmp_path / directory / 'out.pdf'
    target.parent.mkdir()
    source.write_text('# LEGACY_SENTINEL')
    result = subprocess.run(
        [sys.executable, legacy.__file__, str(source), str(target), 'LEGACY_HEADER',
         '--verify', '--require-text', 'LEGACY_SENTINEL'],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    from pypdf import PdfReader
    assert 'LEGACY_SENTINEL' in ''.join(page.extract_text() for page in PdfReader(target).pages)


@pytest.mark.parametrize('mode', ['html', 'svg'])
def test_url_text_attributes_stay_literal_but_css_resources_are_frozen(tmp_path, mode):
    (tmp_path / 'good.png').write_bytes(bitmap_bytes())
    policy = resource_policy.ResourcePolicy(tmp_path / 'in.md')
    markup = ('<svg xmlns="http://www.w3.org/2000/svg" title="url(missing-title)" '
              'data-note="url(missing-data)" aria-label="url(missing-label)">'
              '<image href="good.png" style="filter:url(#local)" fill="url(good.png)"/>'
              '</svg>')
    result = getattr(policy, mode)(markup)
    for literal in ('url(missing-title)', 'url(missing-data)', 'url(missing-label)'):
        assert literal in result
    assert 'data:image/png;base64,' in result
    assert 'url(good.png)' not in result
    with pytest.raises(resource_policy.ResourceError, match='missing-css'):
        getattr(policy, mode)('<svg><rect fill="url(missing-css)"/></svg>')


@pytest.mark.integration
def test_real_cli_alt_url_text_is_not_a_resource(tmp_path):
    (tmp_path / 'ok.png').write_bytes(bitmap_bytes())
    source, target = tmp_path / 'alt-url.md', tmp_path / 'alt-url.html'
    source.write_text('![see url(missing)](ok.png)')
    result = subprocess.run(
        [sys.executable, main.__file__, str(source), str(target), 'HEADER_SENTINEL',
         '--format', 'html', '--browser', 'chrome', '--theme', 'blue'],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'alt="see url(missing)"' in target.read_text()
