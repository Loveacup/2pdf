"""Renderer-owned print preparation; Chromium owns actual page fragmentation."""
import json


def page_geometry(page_size):
    # Match CSS @page margins, not Playwright's fallback margins.
    if page_size == 'A4':
        return 210 * 96 / 25.4 - 36 * 96 / 25.4, 297 * 96 / 25.4 - 40 * 96 / 25.4
    width, height = map(int, page_size.split('x'))
    return width - 20 * 96 / 25.4, height - 24 * 96 / 25.4


# Fraction of the printable page height up to which a block is kept unsplit.
KEEP_RATIO = 0.3


def prepare_print_js(page_size):
    width, height = page_geometry(page_size)
    return """
  const layoutErrors = await page.evaluate(({width, height}) => {
    // Keep only short blocks whole. Holding blocks up to most of a page together pushes them to the
    // next page and leaves half-empty pages; longer blocks split, with widows/orphans guarding lines.
    const keepLimit = height * __KEEP_RATIO__;
    const keepIfShort = el => {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const outerHeight = rect.height + parseFloat(style.marginTop) + parseFloat(style.marginBottom);
      el.style.breakInside = outerHeight <= keepLimit ? 'avoid' : 'auto';
    };
    document.querySelectorAll('pre, .callout, blockquote, table, li').forEach(keepIfShort);
    document.querySelectorAll('img').forEach(el => {
      el.style.maxWidth = '100%';
      el.style.maxHeight = Math.floor(height - 32) + 'px';
      el.style.objectFit = 'contain';
    });
    const errors = [];
    document.querySelectorAll('table').forEach((table, index) => {
      table.querySelectorAll('tr').forEach(row => {
        row.style.breakInside = row.getBoundingClientRect().height < height * 0.8 ? 'avoid' : 'auto';
      });
      const bad = Array.from(table.querySelectorAll('th, td')).find(cell => {
        const style = getComputedStyle(cell);
        const fontSize = parseFloat(style.fontSize);
        const innerWidth = cell.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        return fontSize < 10 || (cell.textContent.trim() && innerWidth < fontSize * 2)
          || cell.scrollWidth > cell.clientWidth + 2;
      });
      if (table.getBoundingClientRect().width > width + 2 || bad) {
        errors.push({table: index + 1, cell: bad ? bad.textContent.trim().slice(0, 100) : '',
          width: table.getBoundingClientRect().width,
          reason: 'Table cannot fit readable text within page width; use fewer columns or a wider page.'});
      }
    });
    return errors;
  }, __GEOMETRY__);
  if (layoutErrors.length) {
    console.error('LAYOUT_ERRORS:' + JSON.stringify(layoutErrors));
    await browser.close();
    process.exit(6);
  }
""".replace('__GEOMETRY__', json.dumps({'width': width, 'height': height})).replace('__KEEP_RATIO__', str(KEEP_RATIO))


def print_viewport_js(page_size):
    width, _ = page_geometry(page_size)
    return f"  await page.setViewportSize({{width: {round(width)}, height: 1000}});\n  await page.emulateMedia({{media: 'print'}});"
