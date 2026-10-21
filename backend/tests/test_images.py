from app.config import get_settings
from app.models import StaffRole
from tests.conftest import JPEG_BYTES, PNG_BYTES

ADMIN, PACKER = StaffRole.ADMIN, StaffRole.PACKER
MUG = {"sku": "MUG-001", "slug": "daisy-mug", "name": "Daisy mug", "price": "1850.00"}


def setup_product(client, headers):
    return client.post("/staff/products", json=MUG, headers=headers).json()["id"]


def upload(client, headers, product_id, data=PNG_BYTES, filename="mug.png", **form):
    return client.post(
        f"/staff/products/{product_id}/images",
        files={"file": (filename, data, "image/png")},
        data=form,
        headers=headers,
    )


def test_upload_stores_file_and_shows_its_url(client, staff_headers, storage):
    headers = staff_headers(ADMIN)
    product_id = setup_product(client, headers)

    response = upload(client, headers, product_id, alt_text="Mug, front")

    assert response.status_code == 201
    image = response.json()
    key = image["url"].removeprefix(get_settings().s3_public_base_url + "/")
    assert key.startswith(f"products/{product_id}/") and key.endswith(".png")
    assert storage.files[key] == (PNG_BYTES, "image/png")
    assert image["alt_text"] == "Mug, front"

    public = client.get("/products/daisy-mug").json()
    assert [i["url"] for i in public["images"]] == [image["url"]]


def test_type_comes_from_the_file_not_its_name(client, staff_headers, storage):
    headers = staff_headers(ADMIN)
    product_id = setup_product(client, headers)

    image = upload(client, headers, product_id, data=JPEG_BYTES, filename="photo.png").json()

    assert image["url"].endswith(".jpg")


def test_non_image_is_rejected(client, staff_headers, storage):
    headers = staff_headers(ADMIN)
    product_id = setup_product(client, headers)

    response = upload(client, headers, product_id, data=b"<script>", filename="evil.png")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    assert storage.files == {}


def test_oversized_image_is_rejected(client, staff_headers, storage):
    headers = staff_headers(ADMIN)
    product_id = setup_product(client, headers)
    big = PNG_BYTES + b"\x00" * get_settings().max_image_bytes

    response = upload(client, headers, product_id, data=big)

    assert response.status_code == 422
    assert storage.files == {}


def test_packer_cannot_upload_images(client, staff_headers, storage):
    product_id = setup_product(client, staff_headers(ADMIN))

    assert upload(client, staff_headers(PACKER), product_id).status_code == 403
    assert storage.files == {}


def test_reorder_and_delete_images(client, staff_headers, storage):
    headers = staff_headers(ADMIN)
    product_id = setup_product(client, headers)
    first, second, third = (
        upload(client, headers, product_id, filename=f"{n}.png").json() for n in "abc"
    )

    client.patch(
        f"/staff/products/{product_id}/images/{third['id']}", json={"position": 0}, headers=headers
    )
    order = [i["id"] for i in client.get("/products/daisy-mug").json()["images"]]
    assert order == [third["id"], first["id"], second["id"]]

    response = client.delete(f"/staff/products/{product_id}/images/{third['id']}", headers=headers)
    assert response.status_code == 204
    images = client.get("/products/daisy-mug").json()["images"]
    assert [(i["id"], i["position"]) for i in images] == [(first["id"], 0), (second["id"], 1)]
    assert len(storage.files) == 2
