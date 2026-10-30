def test_create_equipment_preserves_details_on_retrieval(client):
    """R1: equipment details remain available through a separate lookup."""
    payload = {
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
    }

    created = client.post("/equipment", json=payload)
    assert created.status_code == 201
    equipment_id = created.get_json()["id"]

    retrieved = client.get(f"/equipment/{equipment_id}")
    assert retrieved.status_code == 200
    assert retrieved.get_json() == {
        "id": equipment_id,
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "available_units": 2,
        "is_available": True,
    }


def test_list_equipment_contains_each_created_record(client):
    """R1: listing preserves distinct equipment records and their details."""
    first = client.post(
        "/equipment",
        json={"name": "Kayak", "category": "Water Sports", "total_units": 1},
    )
    second = client.post(
        "/equipment",
        json={"name": "Tent", "category": "Camping", "total_units": 3},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    first_id = first.get_json()["id"]
    second_id = second.get_json()["id"]
    assert first_id != second_id

    response = client.get("/equipment")
    assert response.status_code == 200
    records = response.get_json()
    assert len(records) == 2

    by_id = {record["id"]: record for record in records}
    assert set(by_id) == {first_id, second_id}

    assert by_id[first_id]["name"] == "Kayak"
    assert by_id[first_id]["category"] == "Water Sports"
    assert by_id[first_id]["total_units"] == 1
    assert by_id[first_id]["available_units"] == 1

    assert by_id[second_id]["name"] == "Tent"
    assert by_id[second_id]["category"] == "Camping"
    assert by_id[second_id]["total_units"] == 3
    assert by_id[second_id]["available_units"] == 3

def test_equipment_form_creates_record_and_displays_it(client):
    """Equipment entered through the form is saved and shown in the UI."""
    response = client.post(
        "/ui/equipment",
        data={
            "name": "UI Test Tent",
            "category": "Camping",
            "total_units": "3",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.request.path == "/ui/equipment"

    html = response.get_data(as_text=True)
    assert "UI Test Tent" in html
    assert "Camping" in html

    records = client.get("/equipment").get_json()
    assert len(records) == 1
    item = records[0]
    assert item["name"] == "UI Test Tent"
    assert item["category"] == "Camping"
    assert item["total_units"] == 3
    assert item["available_units"] == 3
    assert item["is_available"] is True


def test_home_links_to_working_management_pages(client):
    """The home page provides navigation to each management page."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    for path, heading in [
        ("/ui/equipment", "Equipment"),
        ("/ui/renters", "Renters"),
        ("/ui/rentals", "Rentals"),
    ]:
        assert f'href="{path}"' in html
        page = client.get(path)
        assert page.status_code == 200
        assert heading in page.get_data(as_text=True)


def test_get_nonexistent_equipment_returns_clear_error(client):
    """An unknown equipment ID produces an error instead of a record."""
    response = client.get("/equipment/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Equipment not found"}
    assert client.get("/equipment").get_json() == []