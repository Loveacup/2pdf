"""P0-A behavioral regression coverage: retain pages, fail images, stage delivery."""
import base64
import builtins
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

import md2pdf_chrome as main
import md2pdf_browser as legacy
import verify_pdf
from image_assets import LocalImageError
from pdf_delivery import DeliveryError, staged_pdf

ROOT = Path(__file__).resolve().parent.parent


def bitmap_bytes():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 32, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\x40\x20" * 32) * 32)) + chunk(b"IEND", b""))


def fixed_pdf(path, kinds=("bitmap", "vector", "signature", "tail", "blank")):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    contents = {
        "bitmap": b"q 200 0 0 200 20 20 cm BI /W 1 /H 1 /CS /RGB /BPC 8 ID " + bytes([255, 64, 32]) + b" EI Q",
        "vector": b"0 0 1 rg 20 20 200 200 re f",
        "signature": b"BT /F1 16 Tf 20 100 Td (Signed: Alex) Tj ET",
        "tail": b"BT /F1 16 Tf 20 100 Td (End.) Tj ET",
        "blank": b"",
    }
    for kind in kinds:
        page = writer.add_blank_page(width=300, height=300)
        stream = DecodedStreamObject()
        stream.set_data(contents[kind])
        page[NameObject("/Contents")] = writer._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                               NameObject("/Subtype"): NameObject("/Type1"),
                                               NameObject("/BaseFont"): NameObject("/Helvetica")})})})
    writer.add_outline_item("Keep outline", 0)
    writer.add_metadata({"/Title": "Preserved metadata", "/Subject": "x" * 1200})
    with path.open("wb") as stream:
        writer.write(stream)


@pytest.mark.parametrize("renderer", [main, legacy])
@pytest.mark.parametrize("kinds", [("bitmap", "vector", "signature", "tail", "blank"), ("vector", "signature")])
def test_all_pages_preserved_byte_identically(tmp_path, renderer, kinds):
    from pypdf import PdfReader
    pdf = tmp_path / "fixed.pdf"
    fixed_pdf(pdf, kinds)
    before = pdf.read_bytes()
    assert renderer.remove_blank_pages(pdf) == 0
    assert pdf.read_bytes() == before
    reader = PdfReader(pdf)
    assert len(reader.pages) == len(kinds)
    assert reader.outline[0].title == "Keep outline"
    assert reader.metadata["/Title"] == "Preserved metadata"


@pytest.mark.parametrize("renderer", [main, legacy])
def test_missing_and_unreadable_local_images_fail(tmp_path, renderer, monkeypatch):
    with pytest.raises(LocalImageError) as missing:
        renderer.embed_local_images("![x](missing.png)", tmp_path)
    assert "missing.png" in str(missing.value)
    image = tmp_path / "unreadable.png"
    image.write_bytes(bitmap_bytes())
    original_read = Path.read_bytes
    def deny(path):
        if path == image:
            raise PermissionError("denied")
        return original_read(path)
    monkeypatch.setattr(Path, "read_bytes", deny)
    with pytest.raises(LocalImageError) as unreadable:
        renderer.embed_local_images("![x](unreadable.png)", tmp_path)
    assert "unreadable.png" in str(unreadable.value)


@pytest.mark.parametrize("renderer", [main, legacy])
def test_embedding_preserves_remote_policy_and_image_content(tmp_path, renderer):
    image = tmp_path / "local.png"
    image.write_bytes(bitmap_bytes())
    embedded = renderer.embed_local_images("![red](local.png)", tmp_path)
    assert base64.b64encode(image.read_bytes()).decode() in embedded
    for src in ("https://example.invalid/a.png", "http://example.invalid/b.png", "data:image/png;base64,AA=="):
        original = f"![unchanged]({src})"
        assert renderer.embed_local_images(original, tmp_path) == original


def test_strict_accepts_image_only_page_and_optional_skips(tmp_path):
    pdf = tmp_path / "bitmap.pdf"
    fixed_pdf(pdf, ("bitmap",))
    result = verify_pdf.verify(pdf)
    assert not verify_pdf.failed(result, strict=True)
    assert result["summary"]["warn"] == 1
    assert any(c["status"] == "skipped" and not c["required"] for c in result["checks"])


def test_missing_body_sentinel_and_invalid_pdf_fail_strict(tmp_path):
    pdf = tmp_path / "signature.pdf"
    fixed_pdf(pdf, ("signature",))
    assert not verify_pdf.failed(verify_pdf.verify(pdf, required_text=["Signed: Alex"]), strict=True)
    assert verify_pdf.failed(verify_pdf.verify(pdf, required_text=["Missing body sentinel"]), strict=True)
    pdf.write_bytes(b"not a PDF" * 300)
    assert verify_pdf.failed(verify_pdf.verify(pdf), strict=True)


def test_required_dependency_skips_fail_only_strict(tmp_path, monkeypatch):
    pdf = tmp_path / "valid.pdf"
    fixed_pdf(pdf)
    real_import = builtins.__import__
    def without_pypdf(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("test dependency unavailable")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", without_pypdf)
    result = verify_pdf.verify(pdf)
    assert not verify_pdf.failed(result)
    assert verify_pdf.failed(result, strict=True)
    assert result["summary"]["required_skipped"] > 0
    assert all(c["reason"] for c in result["checks"] if c["status"] == "skipped")


def test_strict_mermaid_reconciliation_is_required_only_for_diagrams(tmp_path):
    pdf = tmp_path / "valid.pdf"
    fixed_pdf(pdf)
    source = tmp_path / "diagram.md"
    source.write_text("```mermaid\nflowchart LR\nA --> B\n```\n")
    result = verify_pdf.verify(pdf, source)
    assert not verify_pdf.failed(result)
    assert verify_pdf.failed(result, strict=True)


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", ["render", "invalid", "sentinel", "verify_error"])
def test_staging_failure_never_publishes(tmp_path, existing, failure):
    target = tmp_path / "output.pdf"
    if existing:
        target.write_bytes(b"previous target sentinel")
    source = tmp_path / "input.md"
    source.write_text("body")
    with pytest.raises((DeliveryError, RuntimeError)):
        with staged_pdf(target, source, verify=True, strict=True,
                        required_text=["absent"] if failure == "sentinel" else []) as stage:
            assert stage.parent != target.parent
            if failure == "render":
                fixed_pdf(stage)
                raise RuntimeError("renderer failed after writing")
            if failure == "invalid":
                stage.write_bytes(b"not PDF" * 300)
            else:
                fixed_pdf(stage, ("signature",))
                if failure == "verify_error":
                    source.write_text("```mermaid\nflowchart LR\nA --> B\n```\n")
    assert target.read_bytes() == b"previous target sentinel" if existing else not target.exists()
    assert not list(tmp_path.glob(".2pdf-stage-*"))


def test_staging_success_replaces_only_after_gate(tmp_path):
    target = tmp_path / "output.pdf"
    target.write_bytes(b"previous")
    source = tmp_path / "input.md"
    source.write_text("Signed: Alex")
    with staged_pdf(target, source, strict=True, required_text=["Signed: Alex"]) as stage:
        fixed_pdf(stage, ("signature",))
        new_bytes = stage.read_bytes()
        assert target.read_bytes() == b"previous"
    assert target.read_bytes() == new_bytes


def test_verify_error_policy_rejects_missing_sentinel_without_strict(tmp_path):
    target = tmp_path / "out.pdf"
    target.write_bytes(b"previous")
    source = tmp_path / "in.md"
    source.write_text("Signed: Alex")
    with pytest.raises(DeliveryError):
        with staged_pdf(target, source, verify=True, required_text=["missing"]) as stage:
            fixed_pdf(stage, ("signature",))
    assert target.read_bytes() == b"previous"


def test_renderer_exit_failure_is_not_success_even_with_a_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / "already-written.pdf"
    fixed_pdf(pdf)
    html = tmp_path / "input.html"
    html.write_text("<p>body</p>")
    monkeypatch.setattr(main, "_launch_plan", lambda browser: [("chromium.launch()", "test", "test")])
    monkeypatch.setattr(main, "_node_env", lambda: {})
    monkeypatch.setattr(main.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 1, "", "failed after writing PDF"))
    with pytest.raises(RuntimeError):
        main._render_playwright(html, pdf)


def test_cli_strict_arguments():
    args = main.parse_cli_args(["in.md", "--verify-strict", "--require-text", "body", "--require-text", "end"])
    assert args["verify"] and args["verify_strict"]
    assert args["required_text"] == ["body", "end"]


def test_verifier_cli_missing_dependency_strict(tmp_path):
    pdf = tmp_path / "valid.pdf"
    fixed_pdf(pdf)
    # -S removes site-packages without installing/removing any real dependency.
    command = [sys.executable, "-S", str(ROOT / "scripts/verify_pdf.py"), str(pdf), "--json"]
    normal = subprocess.run(command, capture_output=True, text=True)
    strict = subprocess.run(command + ["--strict"], capture_output=True, text=True)
    assert normal.returncode == 0
    assert strict.returncode != 0
    report = json.loads(strict.stdout)
    assert report["summary"]["required_skipped"] > 0


@pytest.mark.integration
@pytest.mark.parametrize("case", ["image", "missing", "corrupt", "sentinel"])
def test_real_cli_image_and_short_ending(tmp_path, case):
    from pypdf import PdfReader
    (tmp_path / "image.png").write_bytes(bitmap_bytes())
    (tmp_path / "corrupt.png").write_bytes(b"not an image")
    image = "missing.png" if case == "missing" else "corrupt.png" if case == "corrupt" else "image.png"
    source = tmp_path / "sample.md"
    source.write_text(f"![visible]({image})\n\n<div style=\"page-break-before:always\"></div>\n\nSigned: Alex\n")
    target = tmp_path / "target.pdf"
    target.write_bytes(b"previous output sentinel")
    command = [sys.executable, str(ROOT / "scripts/md2pdf_chrome.py"), str(source), str(target),
               "--browser", "auto", "--verify-strict", "--require-text",
               "absent body" if case == "sentinel" else "Signed: Alex"]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if case != "image":
        assert proc.returncode != 0
        assert target.read_bytes() == b"previous output sentinel"
        if case in ("missing", "corrupt"):
            assert image in proc.stderr
    else:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        reader = PdfReader(target)
        assert len(reader.pages) == 2
        assert "Signed: Alex" in reader.pages[-1].extract_text()
        assert reader.pages[0].images
    assert not list(tmp_path.glob(".2pdf-stage-*"))
