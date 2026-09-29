# 2pdf 排版优化路线图

> 本文是基于当前 2pdf 源码、现有文档和固定上游提交的**研究与提案**，不是已实现能力或性能承诺。优先做可度量的渐进修正；在兼容性证据充分前，不替换 Chromium 主链。PDF 合并、拆分、旋转、水印、加密、表单读取/填写及基础提取属于独立能力链，本路线图不迁移、不裁剪它们。

## 结论摘要

1. **P0-A：先保证内容不丢。** 优先停止基于文字长度的页面删除，再补缺图诊断和失败交付质量门；不得以无可抽取文字推断页面空白。
2. **P0-B：再封闭并发和资源边界。** 全格式临时产物独占，同目标并发写入拒绝；默认离线，额外本地资源根及远程来源须显式授权，浏览器层同样执行策略。
3. **P1：逐项改善分页、表格、字体、公式和图表。** 先固定可复现测试环境，再用实际页面和内容核对验收，不以旧页数或文本抽取单独判定质量。
4. **P2：在 Chromium 主链上的改进无法达到目标时，才做单独的分页引擎 spike。** Paged.js 是较低授权摩擦的候选；Vivliostyle 是 AGPL-3.0，需先审查分发/集成义务；WeasyPrint 不作为 macOS CJK 默认替代；Typst 是新的排版/内容管线，不是即插即用 Markdown renderer。

## 现状与源码接缝（事实）

- **HTML/Markdown 构造：** [`build_html()`、`wrap_sections()` 和 `preprocess_markdown()`](../scripts/md2pdf_chrome.py#L267-L352) 将 Markdown 扩展转换结果按 h2/h3 包装，并依赖字符串级 DOM 后处理。`build_html()` 使用 Python `markdown` 的 tables、fenced_code、toc、sane_lists、md_in_html、footnotes 扩展，再用正则将 Mermaid fenced block 改为容器（[`md2pdf_chrome.py#L513-L574`](../scripts/md2pdf_chrome.py#L513-L574)）。这使分页行为依赖当前 HTML 结构与这些正则/包装边界。
- **分页：** 文档记录 CSS baseline（标题、列表、段落 widow/orphan、Mermaid avoid break）后由 JS 收集 `offsetTop`/高度，模拟 970px 页面边界，并按元素高度、溢出比例和留白阈值修改 break 样式，另作 heading 与首内容配对（[`md2pdf-details.md#L5-L38`](md2pdf-details.md#L5-L38)）。当前 PDF 主路径由 [`_render_playwright()` / `md_to_pdf()`](../scripts/md2pdf_chrome.py#L1317-L1439) 使用 Chromium `page.pdf()`；auto 只在浏览器启动/渲染失败时降级，Pandoc 救生艇会丢掉 Mermaid、自适应字号与部分样式（[`md2pdf_chrome.py#L1698-L1742`](../scripts/md2pdf_chrome.py#L1698-L1742)）。
- **表格：** 现有 CSS/脚本按列数缩小字号，文档标示 A4 表格 5+ 列 10px、7+ 列 9px；没有以表格语义为中心的跨页标题重复、窄列换行或超长行验收矩阵（[`md2pdf-details.md#L40-L53`](md2pdf-details.md#L40-L53)）。移动版另有 >5 列转字段/值卡片，不能默认推广到 A4 输出（[`md2pdf_chrome.py#L687-L722`](../scripts/md2pdf_chrome.py#L687-L722)）。
- **CJK 与字体：** CSS 字体栈列出 PingFang SC、Hiragino Sans GB、Noto Sans SC、Microsoft YaHei、Source Han Sans CN 等系统字体（[`md2pdf_chrome.py#L763-L770`](../scripts/md2pdf_chrome.py#L763-L770)）；当前文档称 Chromium 的 CJK 正常，并记录 macOS WeasyPrint/Pango 字体嵌入乱码问题（[`md2pdf-details.md#L189-L198`](md2pdf-details.md#L189-L198)）。但 preflight 检查的是 markdown、pypdf、浏览器和 vendored 文件，不检查最终实际解析出的字体/字形覆盖（[`md2pdf_chrome.py#L1933-L1992`](../scripts/md2pdf_chrome.py#L1933-L1992)）。
- **Mermaid/图表：** Mermaid 使用 pinned 本地资源优先、CDN 次选；逐块 parse/render 并 fail-fast，PDF metadata 可记录总数和成功数。现有 verifier 检查 PDF 文件/魔数/页数、Mermaid 源码泄漏/错误文本/图数对账、首页可抽取文本与少量 metadata（[`verify_pdf.py#L59-L113`](../scripts/verify_pdf.py#L59-L113)）。`--verify` 默认只对 error 失败；缺 `pypdf` 的页面级检查会标成 skipped（[`verify_pdf.py#L109-L113`](../scripts/verify_pdf.py#L109-L113)、[`verify_pdf.py#L139-L164`](../scripts/verify_pdf.py#L139-L164)）。
- **资产与并发：** Markdown 本地图片通过 regex 查找、读取完整文件、Base64 内嵌；URL/data URI 跳过，文件不存在时保留原引用（[`embed_local_images()`](../scripts/md2pdf_chrome.py#L179-L195)）。渲染 HTML 路径固定为系统临时目录下 `<stem>.html`，Playwright Node 脚本为固定 `pw_render.js`（[`md_to_pdf()`](../scripts/md2pdf_chrome.py#L1390-L1418)、[`_render_playwright()`](../scripts/md2pdf_chrome.py#L1317-L1370)）。这是并发隔离问题的明确代码接缝；此处不声称已在并发运行中复现故障。
- **后处理边界：** 空白页清理按页文本长度移除空页和末页少于 50 字符页（[`remove_blank_pages()`](../scripts/md2pdf_chrome.py#L1443-L1481)）；扫描件/纯图页存在被误判风险，应以原始版面对照后才能决定删除，不应把“页面抽不到文本”等同于空白页。

## 上游源码研究（事实、许可与采用约束）

这些固定 SHA 均通过 `gh api repos/<owner>/<repo>/commits/HEAD` 核验；下列结论限于链接的实际源文件，不代表它们已经在 2pdf 中运行或验证。许可证为该 SHA 对应仓库 metadata 的 SPDX 标识。

| 项目及固定提交 | 检视到的源码证据 | 许可证与采用约束 |
|---|---|---|
| [Paged.js `breaks.js`](https://github.com/pagedjs/pagedjs/blob/6b0ff8089f472a17247e44671da93d2d931e656e/src/modules/paged-media/breaks.js) / [`chunker/layout.js`](https://github.com/pagedjs/pagedjs/blob/6b0ff8089f472a17247e44671da93d2d931e656e/src/chunker/layout.js) · `6b0ff8089f472a17247e44671da93d2d931e656e` | 将 CSS `break-before/after` 规则映射到节点属性；布局通过 overflow、break token、被迫分页队列及图片加载后再判断内容边界。其仓库还包含 `specs/breaks`、`specs/tables` 的分页案例。 | **MIT**。可作为 CSS 分页 polyfill 候选和测试目录参考；集成仍需核对对应分发包、依赖和浏览器版本。它同样在浏览器 DOM 上分页，并非消除 Chromium 或样式兼容问题的证据；不要因测试用例存在就推断所有 2pdf Markdown 特性无损。仓库许可：[LICENSE.md](https://github.com/pagedjs/pagedjs/blob/6b0ff8089f472a17247e44671da93d2d931e656e/LICENSE.md)。 |
| [Vivliostyle `break-position.ts`](https://github.com/vivliostyle/vivliostyle.js/blob/43711c9c11a09e928dad848144e85eedbf3a3e7c/packages/core/src/vivliostyle/break-position.ts) / [`table.ts`](https://github.com/vivliostyle/vivliostyle.js/blob/43711c9c11a09e928dad848144e85eedbf3a3e7c/packages/core/src/vivliostyle/table.ts) · `43711c9c11a09e928dad848144e85eedbf3a3e7c` | 有显式断点 penalty/overflow 计算；表格单元格、rowspan、行内断点和未完成 cell 内容都有专门逻辑。这表明复杂跨页表格需协同评估整行和单元格，而非单个节点高度规则。 | **AGPL-3.0**。若考虑复用代码或将其作为分发依赖，先由维护者审查 AGPL 对网络服务/分发及衍生作品的义务；在许可决定前只借鉴公开行为/测试思路，不复制实现。仓库许可：[LICENSE](https://github.com/vivliostyle/vivliostyle.js/blob/43711c9c11a09e928dad848144e85eedbf3a3e7c/LICENSE)。 |
| [WeasyPrint `layout/table.py`](https://github.com/Kozea/WeasyPrint/blob/4106b87b908cb1ce609e1eb2dab84ac9bbd769bc/weasyprint/layout/table.py) · `4106b87b908cb1ce609e1eb2dab84ac9bbd769bc` | `table_layout()` 显式处理 table header/footer、row/cell break-inside、rowspan/colspan 与跨页 continuation，适合作为验收维度对照；不是仅靠缩字号压缩宽表。 | **BSD-3-Clause**。虽许可宽松，另有系统库/Pango/Cairo 部署成本；本仓库当前文档记录 macOS CJK 字体呈现问题，故不建议直接作为默认引擎。许可证：[LICENSE](https://github.com/Kozea/WeasyPrint/blob/4106b87b908cb1ce609e1eb2dab84ac9bbd769bc/LICENSE)。 |
| [Typst 数学表格排版 `math/table.rs`](https://github.com/typst/typst/blob/9f2b6e8715237cb086899a42873660fe744622e8/crates/typst-layout/src/math/table.rs) · `9f2b6e8715237cb086899a42873660fe744622e8` | 该文件是数学排版内部矩阵/对齐结构，不是 Markdown 表格或 MathJax 兼容接口；将单一源文件作为“公式排版优秀”依据会扩大结论。Typst 可作为未来数学密集型文档专用路径的研究对象，须验证输入语法、字体、交叉链接、Mermaid/Obsidian 特性再评估。 | **Apache-2.0**。若将来选型，需评估 Rust 工具分发、Typst 源生成和 Markdown/HTML 特性适配成本；不能在不迁移现有 Markdown contract 的情况下静默替换。许可证：[LICENSE](https://github.com/typst/typst/blob/9f2b6e8715237cb086899a42873660fe744622e8/LICENSE)。 |

## 审核结论与实施边界

本方案按 **P0-A → P0-B → P1 → P2** 分阶段交付。先防止内容损失，再处理隔离与资源边界，最后改善版式。下列接口和行为是待实现合同，不代表当前 CLI 已支持。

2026-09-29 审核实测：临时构造两页 PDF，第一页为可见蓝色矢量图形，第二页为 `Signed: Alex`。直接调用当前 `remove_blank_pages()`，结果为 `before 2 / removed 2 / after 0`。这是函数级复现，不扩大为所有正常转换均会失败；输入均为合成素材。当前规则会删除任意无可抽取文本页，以及少于 50 字的尾页，必须优先处理。

### P0-A — 内容不丢失

范围仅为有效页面保护、缺图诊断、交付质量门；不调分页、不换解析器、不增加数学引擎。

| 工作项 | 实施合同 | 验收 |
|---|---|---|
| 页面保护，第一优先级 | 移除以文字长度判断有效页面的规则。首阶段默认保留所有生成页，不进行推测性删页；多余空白页先从生成阶段修复。未来自动删页须另有可靠空白证据，无法判定则保留。独立 PDF 编辑/表单链不变。 | 纯位图、矢量图、短签名、少字尾页、真正空白页组成固定样本；首阶段全部保留，页面顺序、可见内容、书签和 metadata 不损坏；两页复现应保持两页。既测函数，也跑真实 Markdown→PDF 图片页和短结尾。 |
| 缺图失败 | 本地引用缺失、不可读、解码失败须指出源引用并非零退出，不保留一个看似成功的最终文件。P0-B 前不声称资源访问已隔离。 | 对有图/缺图/损坏图分别运行真实转换，成功样本图片可见，失败样本定位准确，既有目标文件字节不变。 |
| 质量门与交付 | 保留现有 `--verify` 的 error 级失败语义；增加显式严格验收模式，将必需检查的 skipped 视为失败。使用本次暂存产物验收，成功后提交；失败退出非零且不覆盖已有结果，不以文件存在判断成功。 | 缺正文哨兵、非法 PDF、必需依赖缺失应失败；合法图片页不因无文本失败。检查状态和跳过原因可见。抽取文字与页面视觉分别验证，不互相替代。 |

**阶段完成条件：** 上述样本在原路径和新路径的差异有记录；真实渲染通过；无有效页面删除、无失败产物冒充成功。此阶段可独立交付，不依赖 P1。

### P0-B — 隔离、资源访问与可重复运行

前置为 P0-A 已通过；范围覆盖 PDF、PNG、HTML、公众号输出，不只修 PDF 主链。

| 工作项 | 实施合同 | 验收 |
|---|---|---|
| 全格式临时隔离 | 每次调用使用独占临时目录，覆盖 HTML、Node 脚本、分析副本、后处理 `.tmp.pdf`；显式传路径，不按输入 stem 使用共享临时文件。正常退出、异常、可处理取消时清理自己的文件；硬杀不承诺立即清理，但遗留物不可被下次复用。 | 四种格式各跑同 stem、不同内容、不同输出目录的并发转换；每组 10 次，产物仅含自身哨兵。异常和取消不影响外部进程或其它任务。 |
| 最终输出所有权 | 使用按规范化目标路径的原子占用机制；同一最终目标的并发写入立即拒绝其中一个，不排队覆盖。顺序调用保持既有覆盖语义，但仅在新产物验收成功后原子替换；所有权在进程退出后释放，不靠永久哨兵锁文件阻塞后续运行。 | 两个并发任务写同一路径只有一个取得写权限；失败方不修改目标。成功后再次顺序转换可完成；失败转换保留已有文件 hash。不同目标不互相阻塞。 |
| 本地资源根 | 默认仅允许源文件真实父目录；增加可重复的显式额外资源根参数，支持用户授权的 `../assets/`。URL 解码、路径规范化和 symlink 解析后再检查真实根。内部 vendor 属受控资源，不扩大用户文档可访问范围。 | 空格、Unicode、合法额外根成功；未授权 `../`、绝对路径和 symlink 逃逸失败；根外 sentinel 不出现在 HTML/PDF。 |
| 离线资源策略 | 默认离线：远程资源明确失败，不静默留引用。既有远程图使用方式须给迁移提示。Python 资源处理和 Chromium 请求拦截共同执行；范围覆盖图片、CSS、字体、SVG、iframe、脚本及重定向，不只扫描 Markdown image。文档任意脚本不执行；仅放行受控渲染脚本。 | 本地 loopback 请求计数服务验证离线转换零外部请求；覆盖 HTML/CSS/SVG 间接引用及脚本发起请求。离线 vendor 缺失报错，不回退 CDN。四种输出均验证。 |
| 显式远程模式 | 通过显式允许来源清单开启所需 HTTP(S) 资源；每次请求及重定向重新校验来源，不以一次允许 URL 授权其所有跳转。不继承浏览器个人 profile、登录 cookie 或隐式认证。不承诺允许的远端服务内部不转发数据。 | 授权来源图片成功；未授权来源及跨来源重定向被阻止。服务端请求计数与允许清单一致。联网产物与离线产物的资源保证分别报告。 |

**阶段完成条件：** 全格式并发、同目标冲突、取消、资源越界、离线零请求和显式远程模式均有实际命令证据。资源安全不因渲染器降级而失效；不能满足相同策略的 fallback 必须拒绝，而非绕过检查。

### P1 — 逐项改善排版

先建立样例与可复现环境，再按下面各项单独提交；不要同时改分页、字体和解析器。

| 工作项 | 实施合同 | 验收 |
|---|---|---|
| 分页语义 | 样例覆盖页底标题、长段、代码、Callout、图片、长短表、脚注及已有用户分页标记。短块保持相邻，超过一页的内容允许拆分，不以全局 avoid-break 制造溢出。 | 同一环境重复渲染页数和结构稳定；标题与首内容同页、无遮挡裁切、内容完整。修复导致合理页数变化时审核新基线，不要求永远等于旧页数。 |
| 表格 | 覆盖 3/6/8 列、CJK 长单元格、代码、rowspan/colspan、三页长表。验证重复表头；长行允许拆分。默认不删列、不截图化，不把移动卡片策略推广至 A4。 | 正文及数据单元格按输入预期次数核对；重复表头按每页规则单独核对，不要求所有文字仅出现一次。无法满足可读字号和页宽时明确诊断，不无声压缩。 |
| 字体 | 等待 `document.fonts.ready`，但不将 ready/check 或 CSS 字体栈当实际字形命中证明。通过 Chromium 字体使用信息及最终页面检查记录实际字体和 fallback；不打包系统字体、不强制下载。 | 中日韩、全角标点、emoji、上下标样例无缺字方框；记录 OS、字体与浏览器版本。macOS/Windows 分别验收，未跑平台明确未验收。 |
| 数学公式 | 实施前确定 TeX 子集和单一公式引擎；不执行公式中嵌入的 HTML/脚本。失败定位具体公式并非零退出，不交给 Pandoc 隐式降级。 | 分别核对源公式解析数量、成功渲染数量和页面视觉；分式、矩阵、根式、上下标正确，不要求 PDF 文本还原原始 TeX token。普通无公式文档的内容与版式保持兼容，不要求含动态 metadata 的 PDF 字节完全相同。 |
| Mermaid 与图片就绪 | 将字体、图片 decode 和 Mermaid 完成状态纳入打印前条件，保留已有逐块错误和图数对账。 | 图块数与成功数相符，每块实际可见且未裁断；语法错误默认失败。`--allow-diagram-errors` 仍为显式豁免，但报告不宣称所有图已成功。离线样例无需 CDN。 |

**阶段完成条件：** 每项均有变更前后页面证据、内容核对和兼容性结果。黄金样例冻结的是可解释的视觉/语义基线，不把旧缺陷当不可改变的正确输出。

### P2 — 条件触发的引擎研究

仅在 P0/P1 后仍存在明确、可复现且当前 Chromium 路径无法解决的缺口时启动，不列为首阶段必做。

- Paged.js：先做显式 opt-in 原型，复用现有 HTML，默认仍是 Chromium 原链；核对 A4/移动尺寸、CJK、表格、Mermaid、脚注、主题、书签和 metadata。
- Vivliostyle：进入实现或分发前先完成 AGPL 义务与本项目许可兼容性审查；源码研究不等于可复制实现。
- WeasyPrint/Typst：仅评估有明确需求的专用路径。macOS CJK 风险不能未经实测就宣布解决；Typst 需要独立输入转换合同，不是 Markdown renderer 的直接替换。
- 任一候选未通过完整兼容矩阵，不改变默认引擎；PDF 编辑/表单链保持独立，不随排版实验迁移。

## 环境基线与验收纪律

当前 vendor 有版本/hash 清单，但 CI 的 Playwright 安装未固定版本，不能称浏览器已锁定。建立版式基线前固定测试用 Playwright 版本及对应 Chromium，记录 OS、Python 依赖、字体名称/版本、主题、页面尺寸和 vendor hash。字体许可不允许分发时使用受控测试环境而非复制系统字体。

初始化和依赖更新提醒已经独立提供；提醒不是升级授权。不得为本轮优化顺便升级 Mermaid 主版本或替换解析器。运行时保留已有系统浏览器选择；其结果与受控 CI 基线分开报告。

每阶段依次执行：生成合成样本 → 保留缺陷证据 → 实现窄修复 → 行为回归 → 实际 CLI 渲染 → 查看关键页面 → 更新文档。测试只对行为和内容断言，不对源码字符串或提示文案断言。用户原始文件只读，验证输出放独立临时目录。

## 证据与状态

- 上游源码与许可证链接保留固定 SHA；本方案不引用未经测量的性能结论。
- 本地源码引用行号仅用于导航，以函数实际行为为准。
- 本次交付为审核后的方案修订，未实现 P0/P1/P2，也未修改 PDF 编辑、表单或渲染代码。上述两页删除是已观察到的函数级缺陷；其余验收条目是实施要求，不是通过记录。
