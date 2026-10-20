# Changelog

格式：每次行为变更记录 improved / preserved / confirmed，并引用 `references/core-requirements.md` 的 CR ID。

## Unreleased

- **Improved（CR06）**：所有排版格式及 Python 入口默认显示 frontmatter 笔记信息卡；新增显式关闭 `--no-properties`，保留 `--properties`，最后出现的开关生效。无需每次手动补参数。
- **Preserved（CR08, CR13）**：`--no-metadata` 仅控制 PDF metadata；`--byline` 继续独立控制署名字段。源 Markdown 只读，空值不补造，显式关闭不影响正文。
- **Confirmed（CR06, CR09）**：新增默认显示、显式关闭及开关顺序的正文行为回归；完整套件 **291 passed**。真实报告未传 `--properties` 即显示信息卡，21 页 A4，图表 3/3；`--verify-strict` 与显式属性文本哨兵检查通过。
- **Improved（CR12）**：`--preflight` 与 `--setup` 不再检查 pandoc。2.0 已停用 pandoc 救生艇，缺 pandoc 不应让 preflight 报 DEGRADED。

## 2.0.0 — 2026-10-20

**Breaking**：四种输出默认离线、只授权源文件真实父目录；远程资源须 `--allow-origin`，根外资源须 `--resource-root`；文档脚本不执行；`--fallback pandoc` 拒绝。迁移说明见 `SKILL.md` Pitfalls 与 `references/optimization-roadmap.md`。

### 终验修复

- **Improved（CR03, CR09）**：修复 `.SFNS-Bold` 中 `·` 的缺字误报。隐藏系统 UI 字体的名义 cmap 可能缺少标点；CoreText 实际排版会使用内部级联字体。仅对 Chromium 记录的 `.SF` 字体补查排版字形，并拒绝零字形与 LastResort。
- **Improved（CR04, CR06）**：修复深色主题 Callout 正文与代码的对比度。Callout 的固定浅色背景配深色正文，主题代码背景与语法颜色保持至少 4.5:1。图片宽度限制覆盖所有媒体，公众号保留内联限制；宽图不再撑大 PNG/HTML 页面。
- **Improved（CR04, CR14）**：KaTeX 解析失败只保留原公式错误，不再追加空 TeX 的 DOM 错误。缺失本地图片增加 1 行修复提示，说明路径、源目录与 `--resource-root`。
- **Preserved（CR03–CR09, CR13, CR14）**：真实缺字、公式错误与缺图仍拒绝交付，不覆盖已有目标。默认离线、资源授权、源文件只读、公式对账及显式图表豁免保持。
- **Confirmed（CR04, CR06）**：Callout 继承错误、`gruvbox-dark` 黄色代码背景及非打印输出宽图溢出，在 `a75fd4c` 中已存在。字体误报与公式重复错误来自本版新增质量门。
- **Confirmed（CR03, CR04, CR06, CR09, CR14）**：完整套件 **289 passed in 203.51s**。18 个主题的实际浏览器对比度测试通过，覆盖全部 Callout 类型与语法颜色。真实缺字仍拒绝交付，错误公式只报告 1 项结构化错误。
- **Confirmed（CR03–CR09, CR14）**：14 份真实文档以默认参数加 `--verify` 全部成功，共 69 页。技术稿与报告的 14 项尺寸/格式复现全部成功；报告 PNG 从 1000 px 恢复为 A4 的 794 px、移动版的 430 px。已查看全部页的接触表，并逐页查看深色代码、Callout、宽图与 `·` 标题。
- **Note**：主题配色调整后，下方 P1 各块所写"与旧基线栅格像素一致"只对当时的提交成立。当前版本普通文档的内容与结构不变，但代码块与 Callout 的配色已改变。

### 真实文档回归修复

- **Improved（CR09）**：`--verify` 的 Mermaid 源码泄漏与错误炸弹检查扣除源文正文（非 mermaid 围栏）中本就写到的同类文字，仅超出部分判错；讨论 Mermaid 报错的文档（如本技能自身 `SKILL.md`、`md2pdf-details.md`）不再被拒绝交付。
- **Improved（CR06）**：分页仅对不超过可印高度 30% 的代码块、Callout、引用、列表项与表格保持整体（原为 80%），更长的块允许拆分，避免整块推页留下半页空白。
- **Preserved（CR05, CR09）**：PDF 中多于源文正文的错误文字/图源码仍判错；标题与首内容相邻、多页块可拆分、widow/orphan 规则不变。
- **Confirmed**：仓库 8 份真实文档在基线与新版的对比渲染中，`SKILL.md`、`md2pdf-details.md` 由质量门失败变为通过；`advanced.md` 从 15 页回到 12 页（基线 11 页）、`optimization-roadmap.md` 11→10 页，接触表目视无半页空白；新增回归测试在旧阈值下失败（8 页）、新阈值下通过（≤6 页）。18 个主题严格验收全部通过，png/html/wechat 与 430×932 公式文档均成功。

### P1 复核修复

- **Improved（CR04, CR06, CR14）**：行内公式遇到不能闭合的未转义美元立即停止该候选并继续扫描，价格不再吞掉后续公式；块引用/Callout 只移除包裹公式的引用层级，保留数学 `>`；沿用 Markdown parser 识别缩进、列表、引用与脚注中的代码美元，恢复源文保持逐字一致。标题 slug 从作者公式源码生成，`equation-x2` 等锚点不再含随机 token。
- **Improved（CR03, CR04, CR09, CR14）**：移动宽表卡片的标题/字段名保留 KaTeX 节点，公式数与成功数按转换后的最终 DOM 重新核对；公众号 CSS 内联保留 KaTeX 字体 at-rule，交付前重新加载实际内联产物，复查资源、图片、实际字体与公式可见性，失败仍不覆盖目标。
- **Preserved（CR01–CR14）**：不升级依赖、不换 parser/KaTeX、不改普通文档的表格文字节点/内联 CSS 结构；无公式样本导出 HTML 的 body 字节完全一致，完整 HTML 除每次运行的 CSP nonce 外完全一致。默认离线、源文件只读、全部页保留、原子交付和显式 Mermaid 错误豁免报告保持。
- **Confirmed（CR03, CR04, CR09, CR14）**：六项均先用真实 CLI 复现再修复；价格旧 exit 3→0 且仅渲染 `x`，引用旧 `>x²>`→`x²`，缩进代码恢复 `$x^2$` 字面；公众号最终产物从 0→20 个 `@font-face`/WOFF2，最终实际字体含 KaTeX；430×932 卡片从只剩 `y²` 恢复 `x²/a²/y²` 三节点，PDF 严格对账 3/3；标题两次随机锚点改为稳定 `equation-x2` 并匹配作者链接。已查看相关前后页面/HTML，命令与输出：`/var/folders/47/8_kft2fx0w3bqlcxcppz_3pm0000gn/T/2pdf-p1-review-euijd5oo/acceptance-summary.json`。
- **Confirmed（CR03–CR14）**：新增 37 项行为回归，渲染用例均标记 integration；上下文回归先 11 failed/1 passed、代码原复现先 1 failed、公众号回归先 5 failed/1 passed，再全部通过。最终完整套件 **260 passed in 178.55s**，含最终 DOM 丢公式、内联后资源/公式失败不交付及普通 HTML 结构兼容。Windows 实机未运行，不声称视觉验收通过。

### 复核修复

- **Improved（CR04, CR09, CR11）**：授权与读取统一按平台解码 file URL，保留 Windows 盘符与转义字符；资源冻结按无 fragment URL 缓存并回填原 fragment，SVG view 不再丢失。外部 SVG `<use>` 因 Chromium data URI 限制明确报源引用并拒绝，要求将 symbol 内联后使用同文档 `#id`，不再成功交付空图。
- **Improved（CR04, CR05, CR09）**：`srcset`/`picture` 的全部候选与普通 `src` 共用浏览器 decode 质量门，包括未选候选，缺失/损坏均定位原始源名；CSS `url()` 只在 style 与已识别 SVG presentation 属性改写，alt/title/ARIA/data 文本保持字面。
- **Improved（CR04, CR06, CR11）**：legacy 与主渲染器共用 fence-first 保护，围栏/行内代码中的图片及 Obsidian 语法不触发预处理；legacy 暂存导航使用 `Path.resolve().as_uri()` 并 JSON 序列化，输出目录中的 `#`、`?`、`%`、空格、引号与 Unicode 不再破坏 URL。
- **Preserved（CR01–CR14）**：不升级依赖、不改 parser/公式/Mermaid/字体与分页策略；默认离线、授权根与跳转检查、全部页保留、源文件只读及原子交付不变，未新增必需参数。
- **Confirmed（CR04, CR09, CR11）**：复跑原复核样本：SVG view HTML/PDF exit 0，HTML 像素采样恢复蓝色 `[0,0,255,255]`；外部 `<use>`、损坏 srcset exit 1 且无新产物并指出源名；legacy 代码示例与 `#` 目录 PDF 通过 `--verify --require-text LEGACY_SENTINEL`，alt 文本原样成功。Windows 使用 nturl2path/PureWindowsPath 在 macOS 验证盘符绝对路径与授权根归属，未声称 Windows 实机验收。命令、结果与探针：`/var/folders/47/8_kft2fx0w3bqlcxcppz_3pm0000gn/T/2pdf-review-fixes-qhy1d9be/`。
  完整套件 **220 passed in 148.11s**，含本次 20 项行为回归；各缺陷的回归族均先出现对应失败再修复。候选集覆盖 srcset-only、picture 与未选密度候选，路径覆盖 `#` 与 `? % ' 中`；原复现首次新证据目录尚未建输出子目录导致的准备失败亦保留在 results.json，建目录后原命令成功。

### P1 — 数学公式

- **Improved（CR02, CR09, CR10, CR14）**：主 CLI 四格式单一 KaTeX 0.16.22，JS/CSS/20 WOFF2 与 MIT LICENSE 精确 sha256 锁定，由显式 setup 下载/修复，普通转换离线。代码先保护，美元分隔遵循 pandoc 边界，转义美元字面显示；公式在页内以 trust:false/throwOnError:true/strict:error 排版，信任依赖命令拒绝。
- **Improved（CR06, CR09, CR14）**：公式失败定位序号/TeX 片段、exit 3，无新产物、不覆盖/不换引擎；MATH_STAT 与 PDF 两个公式计数键由 verifier 按同一源解析器三方对账，严格模式拒绝缺 metadata。
- **Preserved（CR01–CR13）**：现有 Mermaid/parser/deps 不升级；无公式文档不加载数学资源，普通内容/版式不变。P0 资源隔离、原子交付、全部页保留及既有 CLI 参数保持，无新增必需 flag。
- **Confirmed（CR03, CR09, CR14）**：真实默认 bundled Chromium 将旧原样 TeX 改为分式/矩阵/根式/上下标，源/metadata/成功数 4/4/4；错误函数定位 #1、exit 3 无输出；价格、代码/围栏保持。关键前后页面已查看；普通兼容文档仍 1 页。
- **Confirmed（CR03–CR14）**：最终完整套件 **200 passed**；包含分隔符/代码/价格保护、TOC 公式副本、四公式对账、错误/信任依赖命令拒绝、缺/篡改 metadata、离线 HTML 无脚本、vendor hash 与 setup 下载修复回归。普通兼容页与旧基线栅格像素完全一致。

### P1 — Mermaid 与图片就绪

- **Improved（CR03–CR05, CR09）**：字体就绪后布局 Mermaid，打印前强制完成状态、SVG 可见/容器边界及全部图片 decode；移除固定等待与超时继续。PNG/HTML 在初始布局前固定输出视口。IMAGE_STAT 记录解码数量/尺寸。
- **Preserved（CR01–CR13）**：Mermaid 版本/pinned 离线 vendor、逐块报错、图数 metadata 对账、P0 资源/原子交付不变；无 CDN 和任意文档脚本执行。
- **Confirmed（CR03–CR05, CR09）**：离线真实样本基线 1 页→当前 2 页（旧少字尾页删除由 P0-A 停止）；两图均可见且不裁断、图片解码 1/1；错误默认 exit 3 无产物；显式豁免真实报告 1/0/errors=1，metadata 同步，普通兼容文档仍 1 页。
- **Confirmed（CR03–CR12）**：完整套件 171 passed，含默认 bundled Chromium、全格式资源零请求/并发回归及 readiness/显式豁免集成用例。

### P1 — 字体

- **Improved（CR03, CR09）**：全格式等待 fonts.ready，按文本节点采集 CDP 实际字体、PostScript 名、glyphCount/fallback；LastResort/notdef 缺字终止，macOS 另查实际字体 CoreText glyph IDs；FONT_REPORT 记录检查范围及限制，不把 CSS 栈/ready 当命中证明。
- **Preserved（CR01–CR13）**：不打包或强制下载系统字体、不改字体栈、不升级依赖；P0 安全/原子交付和分页/表格合同保持。
- **Confirmed（CR03, CR09）**：macOS 的中日韩、全角标点、emoji、上下标页面无缺字方框，记录 SF NS、PingFang SC、Noto Sans SC、Apple Color Emoji；缺字样本失败无产物，普通文档仍 1 页。Windows 未运行、明确未验收；CDP/cmap 不替代最终视觉核查。
- **Confirmed（CR03–CR12）**：完整套件 169 passed，含全格式既有回归、实际字体记录和缺字失败集成用例。

### P1 — 表格

- **Improved（CR04, CR08）**：取消按列数缩至 9px 的策略；A4 保留语义表格、所有列/单元格和可读字号，固定页宽换行、显式重复表头、超长行允许拆分。小于 10px、单元格内宽不足两字宽或横向溢出时定位表/单元格并拒绝交付。
- **Preserved（CR01–CR13）**：移动卡片只在移动布局使用；不删列、不截图，不升级 parser/deps，不改变资源隔离、内容保护和原子交付。
- **Confirmed（CR04, CR08, CR09）**：3/6/8 列、CJK/代码、rowspan/colspan、三页长表及跨页超长单元格实际渲染；旧路径续页无表头，新路径每页一次，数据逐个对账。40 列不可读样本明确失败；普通兼容样本仍 1 页。页面与命令见路线图证据目录。
- **Confirmed（CR03–CR12）**：完整套件 167 passed，含三页逐页表头/全部数据对账、不可读表失败保留既有目标。

### P1 — 分页语义

- **Improved（CR04, CR06, CR08）**：最终打印流使用全级标题/首内容相邻规则；按实际可打印高度仅保留短块，长代码、Callout、列表和表格允许跨页；图片等比适配页面。固定共享合成样本与 Playwright 1.58.2 基线。
- **Preserved（CR01–CR13）**：既有分页标记、parser、主题、字体栈、Mermaid 版本、P0 资源与原子交付边界不变；不删除任何页。
- **Confirmed（CR04, CR08, CR13）**：默认 bundled Chromium 真实 CLI 前后分页样本均 10 页，普通兼容样本均 1 页；页面证据与命令保存在路线图证据目录。行为测试核对标题配对、长块全部哨兵、脚注及重复结构。
- **Confirmed（CR03–CR12）**：完整套件 165 passed；分页样本重复两次页数与逐页文本结构一致。

### setup 浏览器安装防挂死

- **Improved（CR10）**：`--setup`（`maintenance.py init` 调用）在 Playwright <1.60 且 Node ≥24.16 时拒绝运行 `playwright install` 并给出升级 Playwright 或换 Node 的指引，不再在解压阶段无限等待（microsoft/playwright#40724、#41000）；其余情况安装最多等待 1800s 后中止。
- **Preserved（CR07, CR10）**：有系统 Chrome 时 bundled 安装失败仍只警告并以 `--browser auto` 跑 smoke；初始化不升级依赖。
- **Confirmed**：本机 Node 26.12.0 + Playwright 1.58.2 实测下载完成后解压挂死 20 分钟；新检测在本机命中，版本边界单测覆盖 1.59.9/1.60.0、24.15/24.16 与未安装 Playwright。

### P0-B — 隔离、资源访问与可重复运行

- **Improved（CR04–CR07, CR09, CR11, CR13）**：PDF/PNG/HTML/公众号共用同文件系统私有暂存与按规范化目标的非阻塞内核所有权；HTML、Node、后处理文件均随调用隔离，成功验收才原子交付。异常与可处理取消清理自己的暂存/子进程，退出释放所有权；硬杀遗留不复用。Python 递归冻结资源，Chromium 独立 context、CSP 与请求拦截共同执行边界。
- **Improved / Breaking（CR04–CR07）**：默认离线、默认只授权源文件真实父目录；新增可重复 `--resource-root DIR` 与 `--allow-origin ORIGIN`，URL 解码、规范化、symlink 及每次跳转后检查。迁移旧 `../assets` 用法时显式授权资源根；远程图请本地化或逐来源授权。文档脚本/事件不再执行；vendor 缺失须显式初始化，不再 CDN 回退。旧 pandoc/Chrome CLI 救生艇因不能实施等价策略而明确拒绝；改用 `--browser chrome/auto` 或安装 bundled Chromium。
- **Preserved（CR01–CR03, CR05, CR08, CR10–CR13）**：PDF 编辑/表单链、Markdown parser、Mermaid 版本、分页、CJK 字体栈、原生书签/tagged 结构、metadata、P0-A 内容保护及 PDF 验收语义不变；用户源文件只读，普通转换不升级依赖。显式远程授权不约束远端服务内部转发行为。
- **Confirmed（CR03–CR09, CR11, CR13）**：四格式各 10 路并发产物仅含各自哨兵；同目标立即拒绝、SIGTERM 取消/异常保留旧产物、其它目标不受影响，后续覆盖成功。根外 `../`、绝对路径、symlink 均拒绝，空格/Unicode/显式额外根成功。loopback 计数证明全格式离线零请求、文档脚本不执行；授权来源成功，未授权来源与跨来源跳转目标零请求。服务计数及真实 CLI 命令保存在路线图所列证据目录。
- **Confirmed（CR03, CR05, CR08–CR12）**：最终完整套件 **163 passed**（含默认 bundled Chromium）；离线套件 130 passed / 33 deselected；P0-B/P0-A/路径真实集成 28 passed / 43 deselected。既有 sample + `--verify`、`run_setup()` 实际离线 smoke 子进程、显式系统 Chrome 的 Mermaid/CJK/高亮 smoke 与 legacy 脚本隔离 smoke 均通过；关键页面已实际转图查看。初轮 5 项浏览器安装前置失败已随环境就绪消除，1 项源引用属性重复已修正。

### P0-A — 内容不丢失

- **Improved（CR04, CR06, CR08, CR09）**：主渲染器与 legacy browser 路径默认保留全部生成页，停止按文字长度删页；本地图片缺失/不可读/浏览器解码失败均报源引用并失败。PDF 先写同文件系统暂存产物，完成后处理与请求的独立进程质量门后才原子交付，失败不改已有目标；引擎退出失败不再因文件存在误报成功。
- **Improved（CR06, CR09）**：新增 `--verify-strict`，必需检查 skipped 也失败；新增可重复 `--require-text TEXT` 正文哨兵。保留 `--verify` 的 error 级失败策略，输出每项状态、必需性与跳过原因；无文本图片页仅提示，不据此失败。
- **Preserved（CR01–CR03, CR05, CR07, CR08, CR10–CR13）**：PDF 编辑/表单链不动；不换 Markdown parser、不升级依赖、不改分页；原生 outline/tagged 结构、metadata、CJK 与源文件只读保持。URL/data URI 策略不变，本阶段不宣称离线、资源隔离或并发互斥。
- **Confirmed（CR04, CR08, CR09）**：固定五页样本旧路径 5→2、新路径 5→5（字节不变）；矢量图+签名复现从 2→0 改为 2→2；真实图片+短尾文档从一页丢签名改为两页完整。有图成功；缺图、损坏图、不可读图失败且已有目标字节不变，新目标不产生失败文件；严格模式缺哨兵、非法 PDF、缺 pypdf 均失败。纯位图无文本页通过严格验收，关键页面已转 PNG 查看。
- **Confirmed（CR03, CR08, CR09）**：离线套件 117 passed（9 deselected）；本阶段 auto/Chrome 集成 4 passed（25 deselected）；系统 Chrome 真实 CJK 文档保留原生 outline、StructTreeRoot 与 metadata。首次全套 119 passed / 5 failed，五项均因 bundled headless shell 尚未安装而失败，待安装完成由主任务补验，不更改默认浏览器合同。

### preflight 与治理基线

- **Improved（CR12）**：`--preflight` 按本次 `--browser` 与 `--format` 判断引擎链是否可用，新增 `engine:<browser>` 检查；默认 `playwright` 缺 bundled Chromium、`chrome` 缺系统 Chrome、`auto` 两者皆缺时为 FAIL（退出码 1），`--format wechat` 缺 `css_inline` 为 FAIL。`ok` 项的 `hint` 为空串，不再显示与状态矛盾的缺失提示。
- **Improved**：新增 `references/core-requirements.md`（CR01–CR13 基线）与本文件；`SKILL.md` frontmatter 补 `version`、`author`。
- **Preserved（CR10, CR12）**：JSON 结构与退出码含义不变；组件级缺失仍为 WARN；`maintenance.py init` 照旧解析 JSON 判断资源就绪。
- **Confirmed**：离线测试套件通过；本机实测缺 Chromium 时默认引擎报 FAIL、`--browser auto` 有系统 Chrome 时仍为可用。

## 1.0.0 — 2026-10-06（`a75fd4c`）

独立仓库发布基线：Markdown→PDF/PNG/HTML/公众号排版链、PDF 编辑与表单链、`maintenance.py init` / `check-updates`、Windows 与 macOS 路径兼容。
