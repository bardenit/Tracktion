"""Combine the pages of a photographed receipt into a single PDF.

A multi-page shop invoice arrives as one photo per page. Storing them as one
PDF means the paperwork for a visit is a single thing to open, download or hand
to a buyer, instead of a loose set of images that only make sense in order.

Pillow is a direct dependency here rather than one inherited from reportlab,
and it is pinned in requirements.txt for that reason.
"""

import io
from typing import Iterable, List, Tuple

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 18  # quarter inch, in points
# Phone cameras produce far more detail than a receipt needs. Capping the long
# edge keeps a six-page visit from turning into a 30 MB document.
MAX_EDGE = 2000
JPEG_QUALITY = 85


def _normalise(data: bytes) -> Tuple[bytes, int, int]:
    """Apply EXIF rotation, cap the resolution, and return JPEG bytes.

    EXIF rotation matters: a phone held sideways records the orientation in a
    tag rather than rotating the pixels, and reportlab does not read that tag,
    so without this every other page lands on its side.
    """
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if max(img.size) > MAX_EDGE:
            img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue(), img.width, img.height


def images_to_pdf(images: Iterable[bytes], title: str = "Service receipt") -> bytes:
    """Render one image per page, scaled to fit and centred."""
    pages: List[bytes] = list(images)
    if not pages:
        raise ValueError("At least one page is required")

    out = io.BytesIO()
    pdf = canvas.Canvas(out, pagesize=letter)
    pdf.setTitle(title)

    for data in pages:
        jpeg, width, height = _normalise(data)
        usable_w = PAGE_WIDTH - 2 * MARGIN
        usable_h = PAGE_HEIGHT - 2 * MARGIN
        scale = min(usable_w / width, usable_h / height)
        draw_w, draw_h = width * scale, height * scale
        pdf.drawImage(
            ImageReader(io.BytesIO(jpeg)),
            (PAGE_WIDTH - draw_w) / 2,
            (PAGE_HEIGHT - draw_h) / 2,
            width=draw_w,
            height=draw_h,
        )
        pdf.showPage()

    pdf.save()
    return out.getvalue()
