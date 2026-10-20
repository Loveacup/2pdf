# 2pdf 核心需求

本文件记录 2pdf 必须持续交付的行为。每项失去都会成为可观察的回归。改变行为前先读；新增、收窄或退役某项时同步更新，并在 `CHANGELOG.md` 记录受影响 ID。退役某项由用户决定。

基线：2026-10-20 从 `a75fd4c` 的实际代码、`SKILL.md`、`README.md`、`references/md2pdf-details.md` 与测试提取。

| ID | 需求 |
|---|---|
| CR01 | **触发边界**：Markdown/Obsidian 排版为 PDF/PNG/HTML/公众号；PDF 合并、拆分、旋转、水印、加密、基础文字/表格提取、简单 OCR、创建 PDF、表单读取与填写。文档→Markdown 结构化解析归 sibling 2md，两技能只交换文件、互不 import。 |
| CR02 | **执行链独立**：按用户目标选链；排版链、PDF 编辑链、表单链之间不静默互换。图表内容错误不触发引擎降级或 pandoc 救生艇。 |
| CR03 | **CJK 安全排版**：Chromium 渲染中日韩文字与全角标点不乱码；字体栈覆盖 macOS 与 Windows 常见 CJK 字体，不打包系统字体。 |
| CR04 | **Obsidian 语法**：26 种 Callout（含折叠）、wikilink、`==高亮==`、任务列表、frontmatter 剥离、本地图片内嵌；本地图片缺失、不可读或浏览器解码失败须指出源引用并非零退出；URL/data URI 保持原策略。代码围栏与行内代码先保护再做文本转换（fence-first），`==>` 等代码内容不被改写。 |
| CR05 | **Mermaid 质量门**：使用 pinned 版本、本地 vendor 优先；逐块 parse/render，任一失败默认 exit 3、报块号与错误、不产出文件；`--allow-diagram-errors` 是唯一显式豁免。PDF metadata 记录图总数与成功数。 |
| CR06 | **CLI 合同**：`md_file [pdf_file] [header_text]` 位置参数；`--format`、`--browser`、`--theme`、`--page-size`、`--sm/--xs/--sm-after/--xs-after`、`--properties`、`--byline`、`--preview`、`--no-metadata`、`--verify`、`--fallback pandoc` 语义保持；新增 `--verify-strict` 与可重复 `--require-text TEXT`（均启用 PDF 验收）。Outline 输出供 agent 二次排版决策。 |
| CR07 | **渲染韧性**：默认 Playwright bundled Chromium；`--browser chrome` 用系统 Chrome；`auto` 依次尝试 bundled → 系统 Chrome →（仅 PDF）pandoc；stderr 打印实际 engine 与 executable。 |
| CR08 | **PDF 后处理**：保留所有生成页，不按文字长度删除纯图、矢量、短尾或真正空白页；保留 Chromium 原生书签与 tagged 结构；无原生书签时才用 pypdf 补书签；frontmatter 映射 PDF metadata，`/Author` 仅在源文显式声明时写入；`--no-metadata` 关闭整步。 |
| CR09 | **交付质量门**：PDF 在同文件系统暂存，成功渲染、基础格式检查与请求的质量门通过后才原子替换目标；失败非零退出且保留已有目标字节。`--verify` 在独立进程检查文件魔数/大小、页数、Mermaid 源码泄漏、错误文本、图数对账与 metadata，error 级失败；`--verify-strict` 还拒绝必需检查 skipped，显示状态与原因；`--require-text` 检查显式正文哨兵。合法无文本图片页不作为错误。 |
| CR10 | **环境维护**：`maintenance.py init` 复用健康的 `~/.venvs/pdf-skill`，拒绝改写非 venv 目录或启用系统 site-packages 的环境；`check-updates` 只查询官方元数据并提醒，从不安装；普通转换不升级依赖。 |
| CR11 | **跨平台**：macOS 与 Windows 路径（空格、Unicode、引号）正确转义；使用平台临时目录，不硬编码 `/tmp`、用户目录或 CLI 专属路径。 |
| CR12 | **preflight 合同**：`--preflight [--json]` 不渲染；退出码 0 可用或仅 WARN、1 存在 FAIL、2 指定源文档不存在；JSON 含 `checks[{name,status,hint}]` 与 `overall ∈ ok/degraded/fail`。 |
| CR13 | **源文件只读**：用户原始 Markdown 与资源不被修改；输出只写到推导或指定的目标路径。 |
