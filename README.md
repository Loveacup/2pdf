# 2pdf Skill

PDF 排版与操作技能，为 Claude Code / Codex / Cursor / Hermes 提供 PDF 编辑、提取、表单填写和 Markdown 排版能力。

> **源仓库**: [Loveacup/2pdf](https://github.com/Loveacup/2pdf) · 可公开获取的独立技能
> **许可**：仓库公开不代表采用开源许可；请遵循本仓库现有 `LICENSE.txt` 条款。
> **首次使用**：在仓库根目录运行 `python3 scripts/maintenance.py init`；检查依赖升级提醒用 `python3 scripts/maintenance.py check-updates`。检查只报告，不安装或升级依赖。

## 核心功能

**Markdown → PDF**
将 Obsidian 风格 Markdown 转换为专业排版的 PDF/PNG/HTML/公众号。通过 Chromium 渲染，支持中日韩文字、Mermaid 图表、KaTeX 公式（`$…$` / `$$…$$`）、26 种 Callout 样式。内置 Relay 工作流，自动分析文档结构并优化排版。

**2.0 起的默认安全行为**：
- 默认离线，只读取源文件所在目录内的资源。引用上级或其他目录的图片用 `--resource-root DIR` 授权；远程图片本地化，或用 `--allow-origin https://域名` 逐来源授权。
- 文档内的脚本不执行；`--fallback pandoc` 已停用，改用 `--browser chrome` 或 `--browser auto`。
- 所有生成页都保留；缺图、损坏图、Mermaid 或公式错误会报出具体位置并失败，失败时不覆盖已有输出。
- `--verify` 校验通过后才原子替换目标文件；`--verify-strict` 额外拒绝被跳过的必需检查。

**PDF 文档操作**
合并、拆分、旋转页面、提取文本与表格、添加水印、密码保护。

**表单处理**
读取 PDF 表单字段并自动填写。

**OCR 识别**
扫描件文字提取。


## 选哪条执行链

|任务|执行链|
|---|---|
|Markdown / Obsidian → 排版 PDF/PNG/HTML/公众号|`scripts/md2pdf_chrome.py`（排版引擎）|
|合并/拆分/旋转/水印/加密、简单文字表格提取、简单 OCR|`references/pdf-operations.md`|
|填写 PDF 表单|`references/forms.md`|
|文档 → Markdown（含图片资产/视觉转写、Marker 结构化输出）|独立技能 [2md](https://github.com/Loveacup/2md/blob/main/SKILL.md)|

## 目录结构

pdf/
├── SKILL.md                    # PDF 操作与排版工作流
├── scripts/                    # Markdown→PDF 与 PDF 表单脚本
└── references/
    ├── pdf-operations.md       # 合并/拆分/提取/创建
    ├── md2pdf-details.md       # 排版、字号、Mermaid、Callout
    ├── forms.md                # 表单填写指南
    └── advanced.md             # pypdfium2、pdf-lib、疑难排查

在独立 2pdf 仓库根目录运行以下命令：
```bash
# Markdown 转 PDF
python scripts/md2pdf_chrome.py report.md

# 指定输出路径和页眉
python scripts/md2pdf_chrome.py report.md output.pdf "报告标题"

# 智能排版：密集章节缩小字号，尾部变更记录用更小字号
python scripts/md2pdf_chrome.py doc.md --sm "开发路线图" --xs-after "变更历史"

# 默认显示 frontmatter 笔记信息；可另加署名块与首页/图表页预览
python scripts/md2pdf_chrome.py report.md output.pdf "报告标题" \
  --byline --preview ./preview --verify

# 显式关闭笔记信息卡片（不影响 PDF metadata）
python scripts/md2pdf_chrome.py report.md output.pdf --no-properties


# 初始化已有/缺失环境（健康时复用，不改依赖）
python3 scripts/maintenance.py init

# 查询官方包仓库版本；只提醒，不自动升级
python3 scripts/maintenance.py check-updates
python3 scripts/maintenance.py check-updates --json

```

日常转换不会隐式升级依赖。旧版 `md2pdf_chrome.py` 自动自愈路径在缺依赖时会创建环境并安装未固定版本；请显式运行 `maintenance.py init`，不要把依赖安装交给普通转换。

初始化会核验独立 venv、Playwright Chromium 与本地 Mermaid/highlight.js/KaTeX；已有非空非 venv 目录或启用系统 site-packages 的环境会拒绝安装，避免修改错误的解释器。仅缺浏览器或资源时会调用显式 setup；健康环境重复初始化不安装、不升级。Node ≥24.16 搭配 Playwright <1.60 时浏览器安装会在解压阶段挂死，初始化会跳过该安装并提示先升级 Playwright（`npm install --prefix ~ playwright@^1.60`），不再无限等待。

[依赖提醒 workflow](.github/workflows/dependencies.yml) 每周一 08:23 UTC 运行，也可从 GitHub Actions 手动触发；结果更新同一个 Issue。它检查项目固定版本与临时 CI 环境，不代表本机依赖状态，不修改项目依赖。元数据不可用会明确标记并令任务失败。

排版参数以 [SKILL.md 的 Markdown 参数表](SKILL.md#output-formats--resilience) 为准；文档解析请读 [2md 技能](https://github.com/Loveacup/2md/blob/main/SKILL.md)。PDF 渲染优化背景见[路线图](references/optimization-roadmap.md)。

## 环境要求

排版引擎：
- Python 3 + `markdown` 库（`maintenance.py init` 自动建 `~/.venvs/pdf-skill`）
- Node.js + Playwright Chromium（默认引擎），或系统 Google Chrome（`--browser chrome/auto`）
- 可选：`pypdf`、`pdfplumber`、`reportlab`（PDF 操作）

PDF 文档解析已迁至独立 2md 技能；其 MarkItDown 与 Marker 环境不属于本排版/编辑技能。

## 作者

AlexCai
