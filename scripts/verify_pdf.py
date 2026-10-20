#!/usr/bin/env python3
"""PDF delivery gate. Strict mode rejects skipped required checks, not warnings.

Text extraction and visual inspection are separate evidence: an image-only page
is valid. Optional caller-supplied text sentinels check expected body content.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from math_rendering import source_formula_count

MERMAID_RE = re.compile(
    r"graph\s+(TD|LR|TB|RL|BT)\b|sequenceDiagram|flowchart\s+(TD|LR|TB|RL|BT)"
    r"|stateDiagram|classDiagram|erDiagram|gantt\b|pie\s+title"
)


def _fuzzy_pattern(s):
    return "".join(r"\s{1,2}" if c == " " else re.escape(c) + "{1,2}" for c in s)


ERROR_BOMB_RE = re.compile(
    _fuzzy_pattern("Syntax error") + "|" + _fuzzy_pattern("mermaid version"), re.IGNORECASE
)


def _has_frontmatter(md_path):
    try:
        return bool(re.match(r"^---\n", Path(md_path).read_text(encoding="utf-8")))
    except OSError:
        return False


def _normalized_text(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def verify(pdf, src_md=None, required_text=()):
    """Return legacy findings/summary plus explicit check statuses and requiredness."""
    pdf = Path(pdf)
    checks = []

    def check(name, status, reason, required=True):
        checks.append({"name": name, "status": status, "reason": reason, "required": required})

    if not pdf.is_file():
        check("exists", "error", f"PDF 不存在或不是文件: {pdf}")
        return _result(pdf, checks)
    check("exists", "passed", "PDF 文件存在")
    try:
        size = pdf.stat().st_size
        check("filesize", "passed" if size >= 1024 else "error", f"{size}B（至少 1024B）")
        with pdf.open("rb") as stream:
            magic = stream.read(5)
        check("magic", "passed" if magic == b"%PDF-" else "error", "PDF 文件头检查")
    except OSError as exc:
        check("read", "error", f"无法读取: {exc}")
        return _result(pdf, checks)

    try:
        from pypdf import PdfReader
    except ImportError:
        for name in ("pages", "mermaid_leak", "mermaid_bomb", "diagram_count", "math_count", "required_text"):
            check(name, "skipped", "pypdf 未安装，无法完成页级检查", name != "required_text" or bool(required_text))
        return _result(pdf, checks)

    try:
        reader = PdfReader(str(pdf))
        pages = reader.pages
        check("pages", "passed" if pages else "error", f"{len(pages)} 页")
        texts = [unicodedata.normalize("NFKC", p.extract_text() or "") for p in pages]
        for name, pattern in (("mermaid_leak", MERMAID_RE), ("mermaid_bomb", ERROR_BOMB_RE)):
            hits = [i + 1 for i, text in enumerate(texts) if pattern.search(text)]
            check(name, "error" if hits else "passed", f"命中页 {hits}" if hits else "未检出")
        # No extractable text is a diagnostic, never proof of missing visual content.
        if texts and not texts[0].strip():
            check("first_page", "warn", "首页无可提取文本；纯图/矢量页可合法，须另看页面", False)
        else:
            check("first_page", "passed", "首页有可提取文本", False)
        body = _normalized_text("\n".join(texts))
        for sentinel in required_text:
            found = _normalized_text(sentinel) in body
            check("required_text", "passed" if found else "error", f"正文哨兵 {sentinel!r}")
        meta = reader.metadata or {}
        if src_md and _has_frontmatter(src_md):
            present = bool(meta.get("/Title") or meta.get("/Author"))
            check("pdf_metadata", "passed" if present else "warn", "源 frontmatter 的 PDF metadata 检查", False)
        expected_diagrams = False
        expected_math = None
        if src_md:
            try:
                source = Path(src_md).read_text(encoding="utf-8")
                expected_diagrams = bool(re.search(r"^\s*(?:`{3,}|~{3,})mermaid\b", source, re.M))
                expected_math = source_formula_count(source)
            except OSError as exc:
                check("source", "skipped", f"无法读取源文件: {exc}")
        total, rendered = meta.get("/JZDiagramTotal"), meta.get("/JZDiagramRendered")
        if total in (None, "") or rendered in (None, ""):
            check("diagram_count", "skipped", "PDF 缺图数 metadata" if expected_diagrams else "源文无 Mermaid 图，无需图数对账", expected_diagrams)
        else:
            check("diagram_count", "passed" if str(total) == str(rendered) else "error",
                  f"源 {total} 个、成功渲染 {rendered} 个")
        math_total, math_rendered = meta.get("/JZMathTotal"), meta.get("/JZMathRendered")
        if math_total is None or math_rendered is None:
            check("math_count", "skipped", "公式数量 metadata 缺失" if expected_math else "源文无公式，无需公式对账", bool(expected_math))
        else:
            try:
                total_number, rendered_number = int(math_total), int(math_rendered)
                reconciled = total_number == rendered_number and total_number >= 0
                if expected_math is not None:
                    reconciled = reconciled and total_number == expected_math
                check("math_count", "passed" if reconciled else "error",
                      f"源解析 {expected_math}，记录 {total_number}，成功渲染 {rendered_number}")
            except (TypeError, ValueError):
                check("math_count", "error", "公式数量 metadata 非合法整数")
    except Exception as exc:
        check("parse", "error", f"PDF 解析失败: {exc}")
    return _result(pdf, checks)


def _result(pdf, checks):
    findings = [(c["name"], c["status"], c["reason"]) for c in checks if c["status"] != "passed"]
    summary = {level: sum(c["status"] == level for c in checks) for level in ("error", "warn", "skipped")}
    summary["required_skipped"] = sum(c["status"] == "skipped" and c["required"] for c in checks)
    return {"pdf": str(pdf), "findings": findings, "summary": summary, "checks": checks}


def failed(result, strict=False, fail_on="error"):
    summary = result["summary"]
    return bool(summary["error"] or (strict and summary["required_skipped"])
                or (fail_on == "warn" and summary["warn"]))


def render_report(result, as_json=False):
    if as_json:
        print(json.dumps({**result, "findings": [
            {"name": name, "level": level, "msg": msg} for name, level, msg in result["findings"]
        ]}, ensure_ascii=False))
        return
    for check in result["checks"]:
        required = "required" if check["required"] else "optional"
        print(f"  [{check['status']}] {check['name']} ({required}): {check['reason']}")
    s = result["summary"]
    print(f"  === error={s['error']} warn={s['warn']} skipped={s['skipped']} required_skipped={s['required_skipped']} ===")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("--src")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on", choices=("warn", "error"), default="error")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-text", action="append", default=[])
    args = parser.parse_args(argv)
    result = verify(args.pdf, args.src, args.require_text)
    render_report(result, args.json)
    return int(failed(result, args.strict, args.fail_on))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
