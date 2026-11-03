"""Image clean-up shared by every reader.

Figures are shown on the page in every theme, including dark ones. An image
with a transparent background (equations exported from Google Docs, logos,
diagrams) would show black lines on a dark page, so transparency is
flattened onto white, the way printed figures look.
"""

from __future__ import annotations

import io


def flatten(data: bytes, ext: str, mask: bytes | None = None) -> tuple[bytes, str]:
    """Return PNG or JPEG bytes with no transparency.

    `mask` is a separate alpha channel, which is how PDFs store transparency.
    Images that are already opaque PNG or JPEG are returned unchanged.
    """
    from PIL import Image

    ext = ext.lower()
    if ext == "jpeg":
        ext = "jpg"
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception:
        return b"", ""
    if mask is not None:
        try:
            alpha = Image.open(io.BytesIO(mask)).convert("L")
        except Exception:
            alpha = None
        if alpha is not None:
            if alpha.size != image.size:
                alpha = alpha.resize(image.size)
            image = image.convert("RGBA")
            image.putalpha(alpha)
    has_alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)
    if not has_alpha and ext in ("png", "jpg") and mask is None:
        return data, ext
    if has_alpha:
        rgba = image.convert("RGBA")
        white = Image.new("RGB", rgba.size, "white")
        white.paste(rgba, mask=rgba.getchannel("A"))
        image = white
    else:
        image = image.convert("RGB")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue(), "png"
