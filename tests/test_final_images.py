"""All-media image sizing through the delivered PNG/HTML/WeChat interfaces."""
import json
import struct
import subprocess
import zlib

import pytest

import md2pdf_chrome
from test_typesetting import render


def wide_image_source(tmp_path):
    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data)))

    width, height = 1000, 80
    image = (b'\x89PNG\r\n\x1a\n'
             + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
             + chunk(b'IDAT', zlib.compress((b'\0' + b'\x20\x60\xb0' * width) * height))
             + chunk(b'IEND', b''))
    (tmp_path / 'wide.png').write_bytes(image)
    source = tmp_path / 'wide.md'
    source.write_text('# Wide image\n\n![A wide chart](wide.png)\n\nImage end.\n')
    return source


@pytest.mark.integration
@pytest.mark.parametrize('page_size, width', [('A4', 794), ('430x932', 430)])
def test_png_wide_image_keeps_requested_page_width(tmp_path, page_size, width):
    source = wide_image_source(tmp_path)
    target = tmp_path / 'output.png'
    result = render(source, target, '--format', 'png', '--page-size', page_size, '--verify')
    assert result.returncode == 0, result.stderr
    actual_width, _ = struct.unpack('>II', target.read_bytes()[16:24])
    assert actual_width == width


@pytest.mark.integration
@pytest.mark.parametrize('fmt', ['html', 'wechat'])
@pytest.mark.parametrize('page_size, width', [('A4', 794), ('430x932', 430)])
def test_exported_image_fits_content_width(tmp_path, fmt, page_size, width):
    source = wide_image_source(tmp_path)
    target = tmp_path / 'output.html'
    result = render(source, target, '--format', fmt, '--page-size', page_size, '--verify')
    assert result.returncode == 0, result.stderr
    script = r'''
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:Number(process.argv[2]),height:1000}});
  await page.goto(process.argv[1]);
  const dimensions = await page.evaluate(async () => {
    const img = document.querySelector('img');
    await img.decode();
    const rect = img.getBoundingClientRect();
    const parent = img.parentElement;
    const style = getComputedStyle(parent);
    return {imageWidth:rect.width, imageHeight:rect.height,
      contentWidth:parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
      scrollWidth:document.documentElement.scrollWidth,
      viewportWidth:document.documentElement.clientWidth,
      inlineMaxWidth:img.style.maxWidth};
  });
  console.log(JSON.stringify(dimensions));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
'''
    inspected = subprocess.run(
        ['node', '-e', script, target.resolve().as_uri(), str(width)],
        env=md2pdf_chrome._node_env(), capture_output=True, text=True, timeout=30,
    )
    assert inspected.returncode == 0, inspected.stderr
    dimensions = json.loads(inspected.stdout)
    assert dimensions['imageWidth'] <= dimensions['contentWidth'] + 1
    assert dimensions['scrollWidth'] == dimensions['viewportWidth'] == width
    # Chromium rounds layout dimensions to 1/64 CSS px.
    assert abs(dimensions['imageHeight'] - dimensions['imageWidth'] * .08) <= 1 / 64
    if fmt == 'wechat':
        assert dimensions['inlineMaxWidth'] == '100%'
