"""Local Markdown image embedding and browser-native decode validation."""
import base64
import mimetypes
import re
from html import escape
from pathlib import Path


class LocalImageError(ValueError):
    """A local source image cannot be read or decoded."""


def embed_local_images(md_text, md_dir):
    def replace(match):
        alt, src = match.groups()
        if src.startswith(("http://", "https://", "data:")):
            return match.group(0)
        path = (Path(md_dir) / src).resolve()
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise LocalImageError(f"Local image {src!r}: {exc}") from exc
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        uri = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        # Preserve the source reference through embedding so decode errors identify it.
        return (f'<img alt="{escape(alt, quote=True)}" src="{uri}" '
                f'data-jz-local-source="{escape(src, quote=True)}">')

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace, md_text)


def local_image_check_js():
    """Run before producing any artifact; do not change remote/data URI policy."""
    return """
  const imageErrors = await page.evaluate(async () => {
    const errors = [];
    await Promise.all(Array.from(document.querySelectorAll('img[data-jz-local-source]')).map(async img => {
      try {
        await img.decode();
        if (!img.naturalWidth || !img.naturalHeight) throw new Error('empty image');
      } catch (error) {
        errors.push({ source: img.getAttribute('data-jz-local-source'), reason: String(error) });
      }
    }));
    return errors;
  });
  if (imageErrors.length) {
    console.error('LOCAL_IMAGE_ERRORS:' + JSON.stringify(imageErrors));
    await browser.close();
    process.exit(4);
  }
"""
