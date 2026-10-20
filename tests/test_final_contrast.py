"""Readability contracts measured from Chromium's actual CSS cascade."""
import json
import re
import subprocess

import pytest

import md2pdf_chrome as main
from themes import list_themes, load_theme


@pytest.mark.integration
@pytest.mark.parametrize('theme', list_themes())
def test_theme_callouts_and_syntax_have_readable_computed_colors(tmp_path, theme):
    source = tmp_path / 'contrast.md'
    callouts = '\n\n'.join(
        f'> [!{kind}]{fold} {kind}\n'
        '> Body sentinel **strong sentinel** *emphasis sentinel* '
        '[link sentinel](#target) `inline sentinel`\n>\n> - List sentinel'
        for kind in main.CALLOUT_STYLES for fold in ('', '-', '+')
    )
    source.write_text(
        '# Contrast\n\nInline `code sentinel`.\n\n' + callouts +
        '\n\n```python\n# comment sentinel\nclass Example:\n'
        '    def method(self, value=True):\n'
        '        return "string sentinel", 42\n```\n\n'
        '```text\nunhighlighted code sentinel\n```\n', encoding='utf-8')
    target = tmp_path / 'contrast.html'
    target.write_text(main.build_html(source, '', theme=theme), encoding='utf-8')
    syntax_css = (main.HLJS_STYLES_DIR / f'{load_theme(theme).hljs_theme}.min.css').read_text()
    syntax_css = re.sub(r'/\*.*?\*/', '', syntax_css, flags=re.DOTALL)
    token_selectors = [
        selector.strip()
        for group in re.findall(r'([^{}]+)\{[^{}]*\bcolor:', syntax_css)
        for selector in group.split(',')
    ]
    script = r"""
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(process.argv[1]);
    await page.evaluate(() => document.fonts.ready);
    const result = await page.evaluate(tokenSelectors => {
      // Exercise every selector in the shipped highlight stylesheet, including
      // nested meta/string and title/class variants absent from Python's grammar.
      const code = document.querySelector('pre code');
      const samples = [];
      for (const selector of tokenSelectors) {
        const parts = selector.trim().split(/\s+/);
        if (!parts.every(part => /^\.[\w.-]+$/.test(part)) ||
            !parts.some(part => part.includes('hljs-'))) continue;
        let parent = code;
        for (const part of parts) {
          const span = document.createElement('span');
          span.className = part.slice(1).split('.').join(' ');
          parent.appendChild(span);
          parent = span;
        }
        parent.textContent = ' token sentinel ';
        samples.push(parent);
      }
      const rgba = value => {
        const values = value.match(/[\d.]+/g).map(Number);
        return [...values.slice(0, 3), values.length > 3 ? values[3] : 1];
      };
      const over = (front, back) => {
        const alpha = front[3] + back[3] * (1 - front[3]);
        return [...front.slice(0, 3).map((v, i) =>
          (v * front[3] + back[i] * back[3] * (1 - front[3])) / alpha), alpha];
      };
      const luminance = rgb => rgb.slice(0, 3).map(v => {
        v /= 255;
        return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
      }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
      const measure = element => {
        const ancestors = [];
        for (let node = element; node; node = node.parentElement) ancestors.push(node);
        let background = [255, 255, 255, 1];
        for (const node of ancestors.reverse()) {
          const style = getComputedStyle(node);
          if (style.backgroundImage !== 'none') throw Error('Unsupported gradient background');
          background = over(rgba(style.backgroundColor), background);
        }
        const color = getComputedStyle(element).color;
        const foreground = over(rgba(color), background);
        const a = luminance(foreground), b = luminance(background);
        return {tag: element.tagName, classes: element.className,
          text: element.textContent.slice(0, 80), color, background,
          ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05)};
      };
      const body = [...document.querySelectorAll('.callout p:not(.callout-title), .callout li, .callout strong, .callout em, .callout a')];
      const codeNodes = [...document.querySelectorAll('pre, code, pre code span')];
      return {callouts: document.querySelectorAll('.callout').length,
        syntaxSamples: samples.length,
        highlighted: document.querySelectorAll('pre code .hljs-keyword').length,
        measurements: [...body, ...codeNodes].map(measure)};
    }, JSON.parse(process.argv[2]));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    probe = subprocess.run(
        ['node', '-e', script, target.as_uri(), json.dumps(token_selectors)], env=main._node_env(),
        capture_output=True, text=True, timeout=90)
    assert probe.returncode == 0, probe.stderr
    result = json.loads(probe.stdout)
    assert result['callouts'] == len(main.CALLOUT_STYLES) * 3
    assert result['syntaxSamples'] >= 20
    assert result['highlighted'] > 0
    failures = [row for row in result['measurements'] if row['ratio'] < 4.5]
    assert not failures, f'{theme}: {json.dumps(failures, indent=2)}'
