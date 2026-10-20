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
            hint = ("\nCheck the image path; place the file beneath the source directory, "
                    "or authorize its directory with --resource-root DIR."
                    if isinstance(exc.__cause__, FileNotFoundError) else "")
            raise LocalImageError(f"Local image {src!r}: {exc}{hint}") from exc
        # Preserve the source reference through embedding so decode errors identify it.
        return (f'<img alt="{escape(alt, quote=True)}" src="{uri}" '
                f'data-jz-local-source="{escape(src, quote=True)}">')

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace, md_text)


def local_image_check_js():
    """Require every embedded document image to decode before delivery."""
    return """
  const imageStatus = await page.evaluate(async () => {
    const errors = [], decoded = [];
    const images = Array.from(document.querySelectorAll('img'));
    const candidates = Array.from(document.querySelectorAll('[data-jz-local-srcset]'))
      .flatMap(element => JSON.parse(element.getAttribute('data-jz-local-srcset')));
    const sources = new Map(candidates.map(candidate => [candidate.uri, candidate.source]));
    const failed = new Set();
    const recordError = (source, error) => {
      if (!failed.has(source)) errors.push({source, reason: String(error)});
      failed.add(source);
    };
    await Promise.all(images.map(async img => {
      try {
        await img.decode();
        if (!img.naturalWidth || !img.naturalHeight) throw new Error('empty image');
        decoded.push({width: img.naturalWidth, height: img.naturalHeight});
      } catch (error) {
        recordError(sources.get(img.currentSrc) || img.getAttribute('data-jz-local-source') ||
                    img.currentSrc.slice(0, 160), error);
      }
    }));
    // Check every authorized candidate, including unselected srcset/picture choices.
    await Promise.all(candidates.map(async candidate => {
      const image = new Image();
      image.src = candidate.uri;
      try {
        await image.decode();
        if (!image.naturalWidth || !image.naturalHeight) throw new Error('empty image');
      } catch (error) {
        recordError(candidate.source, error);
      }
    }));
    return {errors, total: images.length, decoded};
  });
  console.log('IMAGE_STAT:' + JSON.stringify(imageStatus));
  if (imageStatus.errors.length) {
    console.error('LOCAL_IMAGE_ERRORS:' + JSON.stringify(imageStatus.errors));
    await browser.close();
    process.exit(4);
  }
"""
