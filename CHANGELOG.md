# Changelog

格式：每次行为变更记录 improved / preserved / confirmed，并引用 `references/core-requirements.md` 的 CR ID。

## Unreleased

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
