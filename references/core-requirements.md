# 2pdf 核心需求

本文件记录 2pdf 必须持续交付的行为。每项失去都会成为可观察的回归。改变行为前先读；新增、收窄或退役某项时同步更新，并在 `CHANGELOG.md` 记录受影响 ID。退役某项由用户决定。

基线：2026-10-20 从 `a75fd4c` 的实际代码、`SKILL.md`、`README.md`、`references/md2pdf-details.md` 与测试提取。

| ID | 需求 |
|---|---|
| CR01 | **触发边界**：Markdown/Obsidian 排版为 PDF/PNG/HTML/公众号；PDF 合并、拆分、旋转、水印、加密、基础文字/表格提取、简单 OCR、创建 PDF、表单读取与填写。文档→Markdown 结构化解析归 sibling 2md，两技能只交换文件、互不 import。 |
| CR02 | **执行链独立**：按用户目标选链；排版链、PDF 编辑链、表单链之间不静默互换。图表内容错误不触发引擎降级或 pandoc 救生艇。 |
| CR03 | **CJK 安全排版**：Chromium 渲染中日韩文字与全角标点不乱码；字体栈覆盖 macOS 与 Windows 常见 CJK 字体，不打包系统字体、不强制下载。P1 等待 `document.fonts.ready`，通过 CDP 记录实际字体/fallback 与 glyphCount，检测 LastResort/notdef；macOS 另以实际字体 CoreText glyph ID 检查覆盖。字体记录与最终页面视觉共同验收；未跑平台明确未验收，ready/check 不作为字形命中证明。 |
| CR04 | **Obsidian 语法与资源边界**：26 种 Callout（含折叠）、wikilink、`==高亮==`、任务列表、frontmatter 剥离、本地图片内嵌；缺失、不可读或浏览器解码失败指出源引用并非零退出。P0-B 起默认仅源文件真实父目录，可重复 `--resource-root DIR` 扩大授权；URL 解码、规范化、symlink 解析后检查。本地/远程 HTML、CSS、字体、SVG、iframe 递归冻结，任意文档脚本不执行；默认离线，远程资源须逐来源 `--allow-origin ORIGIN`，每次请求及跳转重新校验，不继承 cookie/profile/认证。代码围栏与行内代码先保护再转换（fence-first）。 |
| CR05 | **Mermaid 质量门**：使用 pinned 本地 vendor，缺失失败，不在普通转换时下载或回退 CDN；逐块 parse/render，任一失败默认 exit 3、报块号与错误、不产出文件；`--allow-diagram-errors` 是唯一显式豁免并报告真实 total/rendered/errors，不宣称全部成功。P1 打印前要求字体就绪、Mermaid 完成且图块可见/不溢出、所有图片 decode；超时不继续打印。PDF metadata 记录图总数与成功数。 |
| CR06 | **CLI 合同**：`md_file [pdf_file] [header_text]` 位置参数及格式、主题、尺寸、二次排版、frontmatter、preview、metadata 参数保持。`--verify`、`--verify-strict`、可重复 `--require-text TEXT` 启用 PDF 验收；P0-B 新增可重复 `--resource-root DIR`、`--allow-origin ORIGIN`。`--fallback pandoc` 保留解析但明确拒绝不具相同资源策略的旧救生艇；迁移至 `--browser chrome/auto`。Outline 输出供 agent 二次排版决策。 |
| CR07 | **渲染韧性**：默认 Playwright bundled Chromium；`--browser chrome` 用系统 Chrome；`auto` 尝试 bundled → 系统 Chrome，均使用独立无 cookie 的 context、CSP 与请求拦截；stderr 打印实际 engine 与 executable。P0-B 起不再降级至无法执行同等资源策略的 pandoc/Chrome CLI，所有 Chromium 不可用则失败。 |
| CR08 | **PDF 后处理**：保留所有生成页，不按文字长度删除纯图、矢量、短尾或真正空白页；保留 Chromium 原生书签与 tagged 结构；无原生书签时才用 pypdf 补书签；frontmatter 映射 PDF metadata，`/Author` 仅在源文显式声明时写入；`--no-metadata` 关闭整步。 |
| CR09 | **全格式隔离与交付质量门**：PDF/PNG/HTML/公众号每次使用独占暂存目录（含 HTML、Node 脚本及后处理），正常退出、异常及可处理取消清理；硬杀遗留不复用。规范化目标以非阻塞内核锁独占，同目标并发立即拒绝，进程退出释放；顺序覆盖仅在新产物验收成功后原子替换，失败非零且保留已有目标字节。PDF 保留独立进程 `--verify` error 级失败；`--verify-strict` 拒绝必需检查 skipped，显示状态及原因；`--require-text` 检查显式正文哨兵。合法无文本图片页不作为错误。 |
| CR10 | **环境维护**：`maintenance.py init` 复用健康的 `~/.venvs/pdf-skill`，拒绝改写非 venv 目录或启用系统 site-packages 的环境；`check-updates` 只查询官方元数据并提醒，从不安装；普通转换不升级依赖。 |
| CR11 | **跨平台**：macOS 与 Windows 路径（空格、Unicode、引号）正确转义；使用平台临时目录，不硬编码 `/tmp`、用户目录或 CLI 专属路径。 |
| CR12 | **preflight 合同**：`--preflight [--json]` 不渲染；退出码 0 可用或仅 WARN、1 存在 FAIL、2 指定源文档不存在；JSON 含 `checks[{name,status,hint}]` 与 `overall ∈ ok/degraded/fail`。 |
| CR13 | **源文件只读**：用户原始 Markdown 与资源不被修改；输出只写到推导或指定的目标路径。 |
| CR14 | **数学公式（主排版 CLI）**：PDF/PNG/HTML/公众号采用单一 KaTeX 0.16.22，支持其 TeX 函数子集并使用 strict:error、trust:false、throwOnError:true；信任依赖的 HTML/URL/图片命令拒绝，不执行嵌入 HTML/脚本。代码围栏/行内代码先保护；`$$…$$` 行间、`$…$` 行内按 pandoc tex_math_dollars 边界，`\$` 为字面美元。公式失败报序号/源码片段、exit 3，不降级/不交付；源解析数、渲染数与 PDF `/JZMathTotal`、`/JZMathRendered` 由 verifier 对账。无公式文档不加载公式资源、不改变版式；KaTeX JS/CSS/WOFF2 与 MIT LICENSE 精确版本/sha256 锁定，显式 setup 下载，普通转换离线。 |
