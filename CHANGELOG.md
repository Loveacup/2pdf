# Changelog

格式：每次行为变更记录 improved / preserved / confirmed，并引用 `references/core-requirements.md` 的 CR ID。

## Unreleased

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
