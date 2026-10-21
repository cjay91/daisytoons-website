import pytest

from app.text import slugify


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Daisy ceramic mug", "daisy-ceramic-mug"),
        ("Valentine's Day", "valentines-day"),
        ("  Café — 2 cups!  ", "cafe-2-cups"),
        ("Teacher’s pen", "teachers-pen"),
    ],
)
def test_slugify(text, slug):
    assert slugify(text) == slug
