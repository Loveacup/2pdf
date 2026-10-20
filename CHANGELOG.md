# Changelog

格式：每次行为变更记录 improved / preserved / confirmed，并引用 `references/core-requirements.md` 的 CR ID。

## Unreleased

### preflight 与治理基线

- **Improved（CR12）**：`--preflight` 按本次 `--browser` 与 `--format` 判断引擎链是否可用，新增 `engine:<browser>` 检查；默认 `playwright` 缺 bundled Chromium、`chrome` 缺系统 Chrome、`auto` 两者皆缺时为 FAIL（退出码 1），`--format wechat` 缺 `css_inline` 为 FAIL。`ok` 项的 `hint` 为空串，不再显示与状态矛盾的缺失提示。
- **Improved**：新增 `references/core-requirements.md`（CR01–CR13 基线）与本文件；`SKILL.md` frontmatter 补 `version`、`author`。
- **Preserved（CR10, CR12）**：JSON 结构与退出码含义不变；组件级缺失仍为 WARN；`maintenance.py init` 照旧解析 JSON 判断资源就绪。
- **Confirmed**：离线测试套件通过；本机实测缺 Chromium 时默认引擎报 FAIL、`--browser auto` 有系统 Chrome 时仍为可用。

## 1.0.0 — 2026-10-06（`a75fd4c`）

独立仓库发布基线：Markdown→PDF/PNG/HTML/公众号排版链、PDF 编辑与表单链、`maintenance.py init` / `check-updates`、Windows 与 macOS 路径兼容。
