from app.models import StaffRole

ADMIN = StaffRole.ADMIN
MUG = {"sku": "MUG-001", "slug": "daisy-mug", "name": "Daisy mug", "price": "1850.00"}


def make_product(client, headers, **overrides):
    return client.post("/staff/products", json={**MUG, **overrides}, headers=headers).json()


def test_starter_tags_exist(client):
    tags = client.get("/tags").json()

    slugs = {(t["kind"], t["slug"]) for t in tags}
    assert ("occasion", "avurudu") in slugs
    assert ("recipient", "for-teachers") in slugs
    assert len(tags) == 20


def test_tag_a_product(client, staff_headers):
    headers = staff_headers(ADMIN)
    product = make_product(client, headers)

    response = client.put(
        f"/staff/products/{product['id']}/tags",
        json={"occasions": ["birthday", "thank-you"], "recipients": ["for-her"]},
        headers=headers,
    )

    names = [t["name"] for t in response.json()["tags"]]
    assert names == ["Birthday", "For her", "Thank you"]


def test_unknown_tag_is_rejected(client, staff_headers):
    headers = staff_headers(ADMIN)
    product = make_product(client, headers)

    response = client.put(
        f"/staff/products/{product['id']}/tags", json={"occasions": ["nope"]}, headers=headers
    )

    assert response.status_code == 404
    assert "nope" in response.json()["error"]["message"]


def test_filter_products_by_occasion_and_recipient(client, staff_headers):
    headers = staff_headers(ADMIN)
    mug = make_product(client, headers)
    bear = make_product(client, headers, sku="BEAR-1", slug="teddy-bear", name="Teddy bear")
    client.put(
        f"/staff/products/{mug['id']}/tags",
        json={"occasions": ["birthday"], "recipients": ["for-her"]},
        headers=headers,
    )
    client.put(
        f"/staff/products/{bear['id']}/tags",
        json={"occasions": ["birthday"], "recipients": ["for-kids"]},
        headers=headers,
    )

    def names(query):
        return [p["name"] for p in client.get(f"/products?{query}").json()]

    assert names("occasion=birthday") == ["Daisy mug", "Teddy bear"]
    assert names("occasion=birthday&recipient=for-kids") == ["Teddy bear"]
    assert names("occasion=wedding") == []


def test_new_tag_gets_a_slug_from_its_name(client, staff_headers):
    response = client.post(
        "/staff/tags",
        json={"kind": "occasion", "name": "Vesak Poya"},
        headers=staff_headers(ADMIN),
    )

    assert response.json()["slug"] == "vesak-poya"


def test_duplicate_tag_is_a_conflict(client, staff_headers):
    response = client.post(
        "/staff/tags", json={"kind": "occasion", "name": "Birthday"}, headers=staff_headers(ADMIN)
    )

    assert response.status_code == 409
