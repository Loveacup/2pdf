"""Synthetic, deterministic P1 acceptance corpus (never reads user documents)."""
from pathlib import Path


def samples(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="500" height="180"><rect width="500" height="180" fill="#24618a"/><text x="30" y="90" fill="white" font-size="28">IMAGE_VISIBLE</text></svg>')
    page = '<div style="page-break-before:always"></div>'
    pagination = '# Pagination corpus\n\n' + ''.join(f'FILL_{i:03d} 正文用于分页语义检查。\n\n' for i in range(27))
    pagination += '## HEADING_PAIR\n\nFIRST_CONTENT 哨兵必须跟随标题。\n\n'
    pagination += 'LONG_PARAGRAPH_BEGIN ' + '长段落内容保持完整，允许跨页拆分。 ' * 500 + ' LONG_PARAGRAPH_END\n\n'
    pagination += '```text\n' + ''.join(f'CODE_{i:03d} long code line\n' for i in range(90)) + '```\n\n'
    pagination += '> [!note] CALLOUT_SHORT\n> Short callout body.\n\n> [!note] CALLOUT_LONG\n' + ''.join(f'> CALLOUT_{i:03d} 长提示内容。\n>\n' for i in range(80))
    pagination += '\n![Image](image.svg)\n\n| SHORT_HEAD | VALUE |\n|---|---|\n| SHORT_CELL | 42 |\n\nFootnote reference[^one].\n\n[^one]: FOOTNOTE_VISIBLE\n\n' + page + '\n\nMANUAL_BREAK_END\n'
    tables = '# Tables corpus\n\n'
    for cols in (3, 6, 8):
        tables += f'## COLS_{cols}\n\n|' + '|'.join(f'HEAD_{cols}_{i}' for i in range(cols)) + '|\n|' + '|'.join('---' for _ in range(cols)) + '|\n'
        for row in range(3):
            tables += '|' + '|'.join(f'CELL_{cols}_{row}_{i} 中文长内容测试 `code_{i}`' for i in range(cols)) + '|\n'
        tables += '\n'
    tables += '<table><thead><tr><th colspan="2">SPAN_HEADER</th></tr></thead><tbody><tr><td rowspan="2">ROWSPAN_CELL</td><td>SPAN_A</td></tr><tr><td>SPAN_B</td></tr></tbody></table>\n\n'
    tables += page + '\n\n| REPEATED_HEAD | DATA_HEAD |\n|---|---|\n' + ''.join(f'| ROW_{i:03d} | DATA_{i:03d} 长表数据 |\n' for i in range(84))
    tables += '\n<table><thead><tr><th>LONG_ROW_HEAD</th></tr></thead><tbody><tr><td>' + '<br>'.join(f'LONG_CELL_{i:03d}' for i in range(100)) + '</td></tr></tbody></table>\n'
    fonts = '# Font corpus\n\n中文简体，繁體中文。「全角標點」（！？）：；\n\n日本語：ひらがな カタカナ 漢字。\n\n한국어: 한글 글꼴 확인.\n\nEmoji: 😀 🚀 ✅ ❤️ 👩‍💻\n\nSuperscript x² and subscript H₂O; HTML x<sup>2</sup> H<sub>2</sub>O.\n\nFONT_END\n'
    readiness = '# Readiness corpus\n\n![Image](image.svg)\n\n```mermaid\nflowchart LR\n A[开始] --> B[DIAGRAM_ONE]\n```\n\n' + page + '\n\n```mermaid\nsequenceDiagram\n participant A as DIAGRAM_TWO\n participant B as 完成\n A->>B: ready\n```\n\nREADY_END\n'
    math = r'''# Math corpus

Inline $x_i^2 + y^{n+1}$ and literal \$5, price $20 and $30.

$$\frac{1}{2}+\sqrt{x^2+1}$$

$$\begin{pmatrix}a & b \\ c & d\end{pmatrix}$$

$$\sum_{i=1}^{n} i^2$$

`$code$` stays code.

```text
$$not_formula$$
```

MATH_END
'''
    values = {'pagination': pagination, 'tables': tables, 'fonts': fonts, 'readiness': readiness, 'math': math,
              'ordinary': '# Compatibility\n\n普通正文 COMPAT_BODY with **bold** and `code`.\n',
              'bad-diagram': '# Bad diagram\n\n```mermaid\nflowchart LR\n A[broken\n```\n',
              'bad-math': '# Bad formula\n\n$\\notAFunction{x}$\n'}
    for name, text in values.items():
        (directory / f'{name}.md').write_text(text, encoding='utf-8')
    return {name: directory / f'{name}.md' for name in values}
