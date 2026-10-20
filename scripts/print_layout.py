"""Renderer-owned print preparation; Chromium owns actual page fragmentation."""
import json


def page_geometry(page_size):
    # Match CSS @page margins, not Playwright's fallback margins.
    if page_size == 'A4':
        return 210 * 96 / 25.4 - 36 * 96 / 25.4, 297 * 96 / 25.4 - 40 * 96 / 25.4
    width, height = map(int, page_size.split('x'))
    return width - 20 * 96 / 25.4, height - 24 * 96 / 25.4


def prepare_print_js(page_size):
    width, height = page_geometry(page_size)
    return """
  await page.evaluate(({width, height}) => {
    document.querySelectorAll('pre, .callout, blockquote, table, ul, ol').forEach(el => {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const outerHeight = rect.height + parseFloat(style.marginTop) + parseFloat(style.marginBottom);
      // A keep is only advisory for a block that fits. Never lock a multi-page block.
      el.style.breakInside = outerHeight <= height * 0.8 ? 'avoid' : 'auto';
    });
    document.querySelectorAll('img').forEach(el => {
      el.style.maxWidth = '100%';
      el.style.maxHeight = Math.floor(height - 32) + 'px';
      el.style.objectFit = 'contain';
    });
  }, __GEOMETRY__);
""".replace('__GEOMETRY__', json.dumps({'width': width, 'height': height}))


def print_viewport_js(page_size):
    width, _ = page_geometry(page_size)
    return f"  await page.setViewportSize({{width: {round(width)}, height: 1000}});\n  await page.emulateMedia({{media: 'print'}});"
