"""Local Markdown image embedding and browser-native decode validation."""
import re
from html import escape
from pathlib import Path


class LocalImageError(ValueError):
    """A local source image cannot be read or decoded."""


def embed_local_images(md_text, md_dir, policy=None):
    if policy is None:
        from resource_policy import ResourcePolicy
        policy = ResourcePolicy(Path(md_dir) / "document.md")
    def replace(match):
        alt, src = match.groups()
        try:
            uri = policy.resource(src)
        except ValueError as exc:
            raise LocalImageError(f"Local image {src!r}: {exc}") from exc
        # Preserve the source reference through embedding so decode errors identify it.
        return (f'<img alt="{escape(alt, quote=True)}" src="{uri}" '
                f'data-jz-local-source="{escape(src, quote=True)}">')

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace, md_text)


def local_image_check_js():
    """Require every embedded document image to decode before delivery."""
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
