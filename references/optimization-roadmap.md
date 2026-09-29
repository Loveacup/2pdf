# 2pdf 排版优化路线图

> 本文是基于当前 2pdf 源码、现有文档和固定上游提交的**研究与提案**，不是已实现能力或性能承诺。优先做可度量的渐进修正；在兼容性证据充分前，不替换 Chromium 主链。PDF 合并、拆分、旋转、水印、加密、表单读取/填写及基础提取属于独立能力链，本路线图不迁移、不裁剪它们。

## 结论摘要

1. **P0：先修渲染输入的隔离边界与质量门。** HTML 和临时 Node 脚本当前用固定系统临时路径及源文件 stem 命名，易并发互相覆盖；本地图片被读入内存后 Base64 内嵌，缺失文件静默保留原引用，既没有解析路径 containment，也没有输出前资源闭合检查。
2. **P0：用回归样例约束分页与表格，而非继续增加通用高度阈值。** 现有 JS 预测量加 CSS 规则已相当复杂；以分页失败样例作驱动，优先局部修正 heading/table/code/callout 的语义规则。Paged.js 源码可作为分页断点算法和测试维度的参考，不等于建议整条替换。
3. **P1：把 CJK 字体可用性、数学公式及 Mermaid 图表作为明确的交付检查。** 重点确保等待字体和图表完成、保留可读原生输出，并用实际页面渲染与文本抽取双重验收；不能只凭 PDF 存在、页数或 PDF 文本可抽取判断成功。
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

## 优先级路线

### P0 — 交付可靠性与可复现的分页行为

| 方向 | 建议修改接缝 | 收益与风险 | 兼容要求 | 可量化验收 |
|---|---|---|---|---|
| 临时产物隔离 | 将 `md_to_pdf()` 临时 HTML 与 `_render_playwright()` Node 脚本改为每次调用独占的 `TemporaryDirectory`；显式传入路径并在子进程结束后清理。避免 stem 冲突、共享固定文件被并行覆盖。 | 降低并发任务交叉污染；需确保超时、异常与 Windows 文件句柄关闭后才清理。 | 不改变 CLI、输出文件名、主题、PDF 页码/书签；产物只写入调用拥有的临时目录。 | 同时启动两个同 stem、不同内容的转换各 10 次，20 个 PDF 均能独立通过魔数/页数检查，文本不含另一输入的唯一哨兵；正常及异常结束后不遗留临时文件。 |
| 本地资源封闭 | 扩展 `embed_local_images()` 前后的资源整理：解析 Markdown image/link 与 HTML 导入边界；规范化后的文件路径必须在源目录允许根内，缺失、symlink 越界、不可解码图片明确报错或按显式策略降级，不能静默漏图。限制文件体积/图像数量前先确定可配置合同；不下载远端 URL。 | 消除错图/静默缺图和无意读取根目录外文件；路径/Markdown语法变化需与 Obsidian链接共存。 | 普通相对图片保持显示；远端图当前被保留为远程引用的既有行为需有显式兼容选项或清晰迁移提示，不得默默改成下载。 | 生成测试：正常相对图、空格/Unicode路径、缺图、`../`、symlink 越界和远端 URL；前者可见且引用数正确，后三类按已记录规则报告，测试服务收到 0 请求。转换目录外 sentinel 内容不进入 HTML/PDF。 |
| 分页回归语料与局部规则 | 以 `build_html()` → `_render_playwright()` 的实际产物建立小型 Markdown fixture 集：标题贴页底、短节、长段、代码块、Callout、分页图、混合长短表、跨页 rowspan、宽表、脚注。记录 Chromium/PW 版本、页面尺寸、截图；用 Paged.js 的断点和表格 cases 设计测试类别，而不先替换排版器。 | 防止增加规则修复一个场景却回归其它场景；截图基准受字体/浏览器版本影响，须锁定或按语义断言。 | 保持默认 A4、430×932、主题和用户已有页面标记；超过整页的大元素允许拆分，不能 `break-inside: avoid` 导致溢出/空白。 | 每个 fixture PDF 页数在基准 ±0 页；自动断言标题与首块同页、表格无裁切/重叠、代码/Callout 内容无缺失；基准图视觉差异先人工批准，差异阈值不作为未核对的真值。 |
| 质量门：内容-页面联合核验 | 扩展 `verify_pdf.verify()` 和 CLI 汇总：保留现有 PDF/Mermaid 检查，添加按 fixture 哨兵词核对源文本完整性、空页/页面范围检查；检查 `skipped` 必须在机器结果中阻止严格 CI mode，而非默认当通过。只在 `--verify` 请求时按兼容约定失败，或新增明确 strict 选项。 | 能发现白屏/漏文本/检查依赖缺失；PDF 文本抽取对字形、公式、纯图内容不可靠，不能把它当视觉证明。 | 现有 `--verify` 默认 fail-on error 的 CLI 行为不应不加说明地改成 fail-on warning；正常图片封面与扫描页不应被当空白页删除。 | 构造含可抽取哨兵的 PDF 与缺字/空白/纯图对照：遗漏哨兵、非法页数和严格模式下检查 skipped 必须失败；纯图页保留；JSON 报告列明各项状态。 |

### P1 — 排版质量：表格、字体、数学与图表

| 方向 | 建议修改接缝 | 收益与风险 | 兼容要求 | 可量化验收 |
|---|---|---|---|---|
| 表格分层策略 | 在主题 CSS/表格生成之后、页测量前增加窄策略：尽量重复表头（验证 Chromium print 支持后再启用）、保持行/短表不拆、允许超长行拆分；仅当 A4 宽度仍不可容纳时才提供明确缩字号/横向页/移动卡片策略。跨页 colspan/rowspan 必须通过样例逐步支持。参考 WeasyPrint/Vivliostyle 的“行与 cell remainder”用例，不直接照搬引擎内部实现。 | 避免当前按列数缩字号使数字、代码与 CJK 同比例变小；复杂 rowspan 是风险最高的一类。 | 默认 PDF 不自动转为移动字段卡；不删列、不截断、不得将表格图片化；用户指定移动尺寸时保留既有卡片风格。 | Fixture 覆盖 3/6/8 列、超长 CJK cell、长代码、rowspan/colspan、长表跨 3 页；所有源哨兵出现一次，列数/单元格数一致，字号不低于选定下限或质量门提示需要改布局。 |
| 字体装载与 CJK 字形覆盖 | 在 `page.pdf()` 前等待 `document.fonts.ready` 和字体 `check()`；记录实际命中的字体与候补状态，增加中日韩、全角标点、emoji、上标下标混排 fixture。若某目标系统字体缺失，给可操作提示，不静默把 fallback 等同推荐字体。 | 降低字体晚加载/字形 fallback 造成分页漂移或缺字；不同 OS 字体设计不同，跨平台像素级一致不现实。 | 继续优先 Chromium 系；保持用户机器系统字体策略，不打包系统字体、不改变许可、不强制下载字体。 | macOS + Windows 样例字形截图/文本抽取：中文、日文、韩文、标点及常用数学符号无缺字方框；重复渲染页数相同；实际字体缺失时预检/日志能指出缺失或 fallback。未测平台只记为未验收。 |
| 数学公式入口与降级信号 | 核查 `python-markdown` 对常见 `$...$`/`$$...$$` 是否当前产出数学结构；不要让原文公式仅以分隔符文本进入 PDF。先明确支持的 TeX 子集与公式引擎、加载策略，并要求 fonts ready；无法渲染时 fail-fast 或醒目提示。Typst 另作具备输入转换、书签、图片与 Mermaid 兼容证明的 P2 spike，不拿 Typst 数学表格代码证明 Markdown 数学可直接用。 | 数学更易读、可测；新增 MathJax 等运行库可能带来包体、离线缓存和安全内容处理成本。 | 无公式文档输出保持 byte-for-byte 输入行为在可行范围内稳定；不执行公式里的 HTML/脚本，不把公式失败交给 Pandoc 静默降级。 | 用分式、上下标、矩阵、根式、中文夹公式 fixture；成功输出页面有可见结构且源公式 token/可抽取文字对应完整；渲染失败时非 0 并指出第几个公式；本地离线无网络模式同样通过。 |
| Mermaid / 图表闭环 | 保持已有逐块 parse/render 与 metadata 对账；把 `document.fonts.ready`、图片 load、Mermaid finished 纳入统一 ready 条件；`verify_pdf` 增加 diagram 呈现页面抽样或矢量资源检查，但不以 XObject 计数冒充正确性。 | 发现超时、字形缺失、被分页裁断、图形空白；图表结构可能是矢量/图片，PDF 内容检查有误报风险。 | 默认错误继续 fail-fast；`--allow-diagram-errors` 仍是显式逃生口；未失败的图表主题、色板、图数统计不变。 | 样本中源图块数 = 成功图块数；每块输出有非空绘图区并适配页宽；语法错误绝不生成“成功”PDF；图标题不孤页；离线且本地 Mermaid vendor 可完成。 |
| 页面清理保护 | 修改 `remove_blank_pages()` 的末页“少于 50 字”删除判断，要求再结合可见内容/绘制对象/原页数或限定为确实由 Chromium 生成的空白尾页；优先在生成前避免空白页而非对任意内容 PDF 事后删除。 | 保护纯图封面、签名/表格空白页、少字结尾；变更可能保留旧流程产生的真空页。 | 只作用于 Markdown 生成后的 PDF，不改变用户独立编辑/表单 PDF。 | 纯图、只有签名线、短结尾、真正空白尾页四种 PDF fixture：前三者页数完整保留，最后一种仅在明确确认空白时移除；每项输出前后页数可追踪。 |

### P2 — 候选引擎与更广格式

| 方向 | 触发条件与建议 | 风险、兼容边界 | 验收门槛 |
|---|---|---|---|
| Paged.js opt-in 原型 | P0/P1 后仍有明确分页缺口，再在隔离分支做 `--layout pagedjs` 原型，限于由现有 `build_html()` 生成的 HTML；保留 Chromium 输出默认路径，勿同时改 Markdown parser、主题或后处理。Paged.js 源码优先用来梳理 break-token、forced-break queue、表格断点测试。 | 新增 Node 包及浏览器运行依赖；行为与 Chromium 自带打印分页相互作用；MIT 许可较易评估但仍需核查锁文件、打包许可证与供应链。旧 PDF 的书签/tagging、Mermaid 等必须逐项比对。 | 在同一 fixture 上两个 engine 均输出有效 PDF；默认仍为 Chromium；只有明确选择才启用新路径。Paged.js 只有在 A4/CJK/表格/书签/图表所有必须项通过且不存在无声特性丢失时，才考虑是否将来切换默认。 |
| Vivliostyle 合规评估 | 用户明确要求更专业出版排版特性（running headers、named pages、复杂分页）且 Paged.js 原型不足时再评估。研究成果不能直接复制 AGPL 代码。 | AGPL-3.0 可能影响二进制/网络服务/衍生作品发布；需在任何代码集成、作为依赖发布前由维护者作许可决策。 | 许可确认、依赖发布义务与分发方式先书面明确；符合当前私有许可证及发行合同后才进入原型。 |
| WeasyPrint/Typst 专用路径 | WeasyPrint 只在非 macOS CJK 目标、系统依赖可管理且真实字形验收通过后考虑；Typst 仅在数学/出版密集且可接受独立输入转换合同的场景 spike。 | WeasyPrint 已有文档记录的 macOS CJK 风险未由本次实测消除；Typst 将产生一条新内容表示/排版链，Markdown、Obsidian、Mermaid、链接与主题兼容成本不等同于 renderer 替换。 | 任何新路径必须在当前 Chromium 黄金语料上通过 Mermaid、callouts、脚注、CJK、图片、表格、书签、metadata 和 forms 隔离矩阵；能力差异需在 CLI/文档显式呈现，不能把错误回退成内容缺失。 |

## 维护前置条件

此路线图依赖 2pdf 在独立仓库内可初始化、并能显式检查依赖更新状态。上游研究已有固定提交证据，不代表本机安装版本自动匹配；开始 P0 前先完成该技能约定的初始化和更新检查命令，并确认 pinned 浏览器与 vendor 资产健康。更新提醒只提供版本信息/人工决策，不在日常渲染或提醒时自动升级。此处不重复维护脚本、定时 workflow 或依赖清单设计。

## 建议执行顺序

1. 先实现 P0 临时目录独占、资源 containment 与严格测试 fixture；冻结一份当前 Chromium 输出截图/文本基线。
2. 逐个修复分页边界和 verifier 的可观测缺口；每个规则变化都用 P0 fixture 验收，避免笼统调阈值。
3. 做 P1 表格/CJK/公式/图表的专门样例；已有 Markdown→PDF、主题、样式契约继续兼容。
4. 最后评估 P2 renderer 原型；只有完整兼容矩阵和许可审查通过才讨论默认切换。

## 证据与范围声明

- 当前代码/文档引用以本地 `shared/2pdf/scripts/md2pdf_chrome.py`、`verify_pdf.py`、`references/md2pdf-details.md` 和 `SKILL.md` 的已读范围为据；引用行号用于导航，相关函数行为以固定工作树内容为准。
- 上游链接固定到已核验 commit SHA，以便后续复查差异；不引用博客性能数字，不作“更快/更轻/完全兼容”结论。
- 本次仅研究并写计划；未运行 build、test、lint 或 formatter，也未改变 PDF 编辑、表单、表格提取或其它功能链。
