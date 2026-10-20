"""Chromium font readiness, actual platform-font evidence and missing-glyph guard."""
import ctypes
import json
import re
import sys
import unicodedata


def font_check_js():
    return r"""
  await page.evaluate(async () => { await document.fonts.ready; });
  const fontSession = await context.newCDPSession(page);
  await fontSession.send('DOM.enable');
  await fontSession.send('CSS.enable');
  const fontTree = await fontSession.send('DOM.getDocument', {depth: -1, pierce: true});
  const fontNodes = [];
  function collectFontNodes(node) {
    if (!['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(node.nodeName) &&
        (node.children || []).some(child => child.nodeType === 3 && child.nodeValue.trim())) {
      fontNodes.push({nodeId: node.nodeId, text: node.children.filter(child => child.nodeType === 3).map(child => child.nodeValue).join('')});
    }
    for (const child of node.children || []) collectFontNodes(child);
  }
  collectFontNodes(fontTree.root);
  const usedFonts = new Map();
  const glyphRuns = [];
  for (const {nodeId, text} of fontNodes) {
    const result = await fontSession.send('CSS.getPlatformFontsForNode', {nodeId});
    if (result.fonts.length) glyphRuns.push({characters: Array.from(new Set(text)).join(''), fonts: result.fonts});
    for (const font of result.fonts) {
      const key = font.postScriptName || font.familyName;
      const old = usedFonts.get(key);
      if (old) old.glyphCount += font.glyphCount;
      else usedFonts.set(key, {...font});
    }
  }
  await fontSession.detach();
  const glyphFailures = await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 96; canvas.height = 96;
    const ctx = canvas.getContext('2d', {willReadFrequently: true});
    const checked = new Set(), failures = [];
    function ink(text) {
      ctx.clearRect(0, 0, 96, 96);
      ctx.fillText(text, 8, 64);
      return ctx.getImageData(0, 0, 96, 96).data;
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode, parent = node.parentElement;
      if (!parent || parent.closest('script, style, .katex-mathml') || !parent.getClientRects().length) continue;
      const style = getComputedStyle(parent);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      ctx.font = `${style.fontStyle} ${style.fontWeight} 32px ${style.fontFamily}`;
      const missingMetrics = ctx.measureText('\uffff');
      let missingInk;
      for (const char of node.textContent) {
        if (/^[\s\p{Mark}\p{Control}\p{Format}]$/u.test(char) || /[\uFE00-\uFE0F]/u.test(char)) continue;
        const key = ctx.font + char;
        if (checked.has(key)) continue;
        checked.add(key);
        const metrics = ctx.measureText(char);
        if (metrics.width !== missingMetrics.width || metrics.actualBoundingBoxLeft !== missingMetrics.actualBoundingBoxLeft ||
            metrics.actualBoundingBoxRight !== missingMetrics.actualBoundingBoxRight) continue;
        if (!missingInk) missingInk = ink('\uffff');
        const actual = ink(char);
        if (actual.every((value, i) => value === missingInk[i])) {
          failures.push({character: char, codepoint: 'U+' + char.codePointAt(0).toString(16).toUpperCase(),
                         context: node.textContent.trim().slice(0, 100)});
        }
      }
    }
    return failures;
  });
  const fonts = Array.from(usedFonts.values()).sort((a, b) => a.familyName.localeCompare(b.familyName));
  const lastResort = fonts.filter(font => /lastresort/i.test(font.familyName + font.postScriptName));
  console.log('FONT_REPORT:' + JSON.stringify({fonts, glyphRuns, missing: glyphFailures, lastResort,
    detection: 'CDP actual fonts + rendered notdef comparison; visual review still required'}));
  if (glyphFailures.length || lastResort.length) {
    console.error('MISSING_GLYPHS:' + JSON.stringify({missing: glyphFailures, lastResort}));
    await browser.close(); process.exit(7);
  }
"""


def check_font_report(stdout):
    """Keep diagnostics machine-readable; CoreText checks actual font cmaps on macOS."""
    match = re.search(r'FONT_REPORT:(.*)', stdout)
    if not match:
        raise RuntimeError('Chromium did not return actual font usage evidence')
    report = json.loads(match[1])
    runs = report.pop('glyphRuns', [])
    if sys.platform == 'darwin':
        report['nativeCoverage'] = 'CoreText non-ASCII glyph IDs for actual per-node fonts; ASCII uses Chromium raster guard'
        report['missing'].extend(_coretext_missing(runs))
    else:
        report['nativeCoverage'] = 'unverified; CDP/notdef diagnostics do not replace platform visual acceptance'
    print('FONT_REPORT:' + json.dumps(report, ensure_ascii=False), file=sys.stderr)
    if report['missing'] or report['lastResort']:
        raise RuntimeError('Missing font glyphs: ' + json.dumps(report['missing'], ensure_ascii=False))
    return report


def _coretext_missing(runs):
    cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    ct = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
    ptr = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ptr, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFStringCreateWithCString.restype = ptr
    cf.CFRelease.argtypes = [ptr]
    ct.CTFontCreateWithName.argtypes = [ptr, ctypes.c_double, ptr]
    ct.CTFontCreateWithName.restype = ptr
    ct.CTFontCreateUIFontForLanguage.argtypes = [ctypes.c_uint32, ctypes.c_double, ptr]
    ct.CTFontCreateUIFontForLanguage.restype = ptr
    ct.CTFontGetGlyphsForCharacters.argtypes = [ptr, ctypes.POINTER(ctypes.c_uint16),
                                               ctypes.POINTER(ctypes.c_uint16), ctypes.c_long]
    ct.CTFontGetGlyphsForCharacters.restype = ctypes.c_bool
    fonts, coverage, missing = {}, {}, {}
    try:
        for run in runs:
            # Webfonts have no CoreText-installed face. Chromium's notdef guard applies.
            if any(font['isCustomFont'] for font in run['fonts']):
                continue
            names = [font['postScriptName'] or font['familyName'] for font in run['fonts']]
            for char in run['characters']:
                # System UI faces synthesize some ASCII punctuation outside cmap (e.g. [] on macOS).
                # Chromium's raster/notdef check remains authoritative for those characters.
                if ord(char) < 128 or char.isspace() or unicodedata.category(char) in ('Cc', 'Cf', 'Mn', 'Me'):
                    continue
                found = False
                for name in names:
                    if name not in fonts:
                        if name.startswith('.SF'):
                            fonts[name] = ct.CTFontCreateUIFontForLanguage(3 if 'Bold' in name else 2, 12, None)
                        else:
                            string = cf.CFStringCreateWithCString(None, name.encode(), 0x08000100)
                            try:
                                fonts[name] = ct.CTFontCreateWithName(string, 12, None)
                            finally:
                                cf.CFRelease(string)
                    key = (name, char)
                    if key not in coverage:
                        raw = char.encode('utf-16-le')
                        count = len(raw) // 2
                        characters = (ctypes.c_uint16 * count).from_buffer_copy(raw)
                        glyphs = (ctypes.c_uint16 * count)()
                        ct.CTFontGetGlyphsForCharacters(fonts[name], characters, glyphs, count)
                        coverage[key] = any(glyphs)
                    if coverage[key]:
                        found = True
                        break
                if not found:
                    missing[char] = {'character': char, 'codepoint': f'U+{ord(char):04X}', 'fonts': names}
    finally:
        for font in fonts.values():
            cf.CFRelease(font)
    return list(missing.values())
