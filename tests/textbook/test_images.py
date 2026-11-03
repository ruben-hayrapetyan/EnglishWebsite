"""Glass-box tests for tools/textbook/images.py: figures readable in every theme."""

import io

from PIL import Image

from tools.textbook.images import flatten


def png(mode, size=(4, 2), color=None):
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, "PNG")
    return out.getvalue()


def pixels(data):
    return list(Image.open(io.BytesIO(data)).convert("RGB").getdata())


def test_transparent_png_is_flattened_onto_white():
    data, ext = flatten(png("RGBA", color=(0, 0, 0, 0)), "png")
    assert ext == "png" and set(pixels(data)) == {(255, 255, 255)}


def test_pdf_style_mask_is_applied_then_flattened():
    """PDFs keep transparency in a separate mask; without it equations turn black."""
    black = png("RGB", color=(0, 0, 0))
    mask = png("L", color=0)  # fully transparent
    data, _ = flatten(black, "png", mask)
    assert set(pixels(data)) == {(255, 255, 255)}
    half = png("L", size=(2, 1), color=255)  # a mask of another size is stretched to fit
    data, _ = flatten(black, "png", half)
    assert set(pixels(data)) == {(0, 0, 0)}


def test_opaque_images_are_left_alone():
    data = png("RGB", color=(10, 20, 30))
    assert flatten(data, "png") == (data, "png")
    out = io.BytesIO()
    Image.new("RGB", (3, 3), (1, 2, 3)).save(out, "JPEG")
    assert flatten(out.getvalue(), "jpeg") == (out.getvalue(), "jpg")


def test_unreadable_data_gives_nothing():
    assert flatten(b"not an image", "png") == (b"", "")
