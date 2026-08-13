"""Shared image normalization for uploaded and existing photographs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from PIL import Image, ImageOps


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    width: int
    height: int
    checksum: str
    content_type: str = "image/jpeg"
    extension: str = ".jpg"


def normalization_policy() -> dict[str, int | str]:
    return {
        "format": "JPEG",
        "max_edge": settings.BONES_IMAGE_MAX_EDGE,
        "quality": settings.BONES_IMAGE_JPEG_QUALITY,
    }


def _rgb_image(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def normalize_image(source) -> NormalizedImage:
    """Orient, resize, and encode an uploaded photograph as a compact JPEG."""
    policy = normalization_policy()
    max_edge = policy["max_edge"]
    quality = policy["quality"]
    source.seek(0)
    with Image.open(source) as opened:
        opened.load()
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        image = _rgb_image(image)
        exif = image.getexif()
        output = BytesIO()
        options = {"format": "JPEG", "quality": quality, "optimize": True, "progressive": True}
        if exif:
            options["exif"] = exif.tobytes()
        image.save(output, **options)
        data = output.getvalue()
        width, height = image.size
    source.seek(0)
    return NormalizedImage(data, width, height, hashlib.sha256(data).hexdigest())
