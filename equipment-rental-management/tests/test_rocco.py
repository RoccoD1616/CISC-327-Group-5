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

def test_update_equipment_preserves_unspecified_fields(client):
    """Updating a name retains the equipment's other recorded details."""
    created = client.post(
        "/equipment",
        json={
            "name": "Original Kayak",
            "category": "Water Sports",
            "total_units": 2,
        },
    )
    assert created.status_code == 201
    original = created.get_json()
    equipment_id = original["id"]

    updated = client.put(
        f"/equipment/{equipment_id}",
        json={"name": "Renamed Kayak"},
    )
    assert updated.status_code == 200

    expected = {**original, "name": "Renamed Kayak"}
    assert updated.get_json() == expected

    retrieved = client.get(f"/equipment/{equipment_id}")
    assert retrieved.status_code == 200
    assert retrieved.get_json() == expected


def test_update_nonexistent_equipment_does_not_create_record(client):
    """Updating an unknown ID returns an error without adding equipment."""
    response = client.put(
        "/equipment/999",
        json={"name": "Missing Kayak"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Equipment not found"}

    listing = client.get("/equipment")
    assert listing.status_code == 200
    assert listing.get_json() == []

def test_delete_equipment_removes_only_selected_record(client):
    """Deleting one item preserves another and prevents later retrieval."""
    first = client.post(
        "/equipment",
        json={"name": "Delete Kayak", "category": "Water Sports"},
    )
    second = client.post(
        "/equipment",
        json={"name": "Keep Tent", "category": "Camping"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    deleted_id = first.get_json()["id"]
    retained = second.get_json()

    response = client.delete(f"/equipment/{deleted_id}")
    assert response.status_code == 204

    lookup = client.get(f"/equipment/{deleted_id}")
    assert lookup.status_code == 404
    assert lookup.get_json() == {"error": "Equipment not found"}

    listing = client.get("/equipment")
    assert listing.status_code == 200
    assert listing.get_json() == [retained]

    repeated = client.delete(f"/equipment/{deleted_id}")
    assert repeated.status_code == 404
    assert repeated.get_json() == {"error": "Equipment not found"}
    assert client.get("/equipment").get_json() == [retained]


def test_equipment_form_delete_removes_record_from_page_and_store(client):
    """The UI delete action removes the selected equipment record."""
    created = client.post(
        "/equipment",
        json={"name": "UI Delete Tent", "category": "Camping"},
    )
    assert created.status_code == 201
    equipment_id = created.get_json()["id"]

    before = client.get("/ui/equipment")
    assert "UI Delete Tent" in before.get_data(as_text=True)

    response = client.post(
        f"/ui/equipment/{equipment_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.request.path == "/ui/equipment"
    assert "UI Delete Tent" not in response.get_data(as_text=True)

    assert client.get(f"/equipment/{equipment_id}").status_code == 404
    assert client.get("/equipment").get_json() == []

def test_service_status_changes_persist_without_changing_unit_counts(client):
    """R13: equipment can leave and return to service without changing stock."""
    created = client.post(
        "/equipment",
        json={"name": "Repair Bike", "category": "Bikes", "total_units": 2},
    )
    assert created.status_code == 201
    equipment_id = created.get_json()["id"]

    for service_status in (False, True):
        updated = client.patch(
            f"/equipment/{equipment_id}/status",
            json={"is_available": service_status},
        )
        assert updated.status_code == 200
        assert updated.get_json()["is_available"] is service_status

        availability = client.get(f"/equipment/{equipment_id}/availability")
        assert availability.status_code == 200
        assert availability.get_json() == {
            "equipment_id": equipment_id,
            "is_available": service_status,
            "available_units": 2,
            "total_units": 2,
        }

        record = client.get(f"/equipment/{equipment_id}").get_json()
        assert record["is_available"] is service_status
        assert record["available_units"] == 2
        assert record["total_units"] == 2


def test_availability_tracks_checkout_and_return(client):
    """Availability reflects rental activity while service status stays separate."""
    equipment = client.post(
        "/equipment",
        json={"name": "Single Kayak", "category": "Water Sports", "total_units": 1},
    )
    renter = client.post(
        "/renters",
        json={"name": "Test Renter", "email": "test@example.com"},
    )
    assert equipment.status_code == 201
    assert renter.status_code == 201
    equipment_id = equipment.get_json()["id"]
    renter_id = renter.get_json()["id"]

    initial = client.get(f"/equipment/{equipment_id}/availability")
    assert initial.status_code == 200
    assert initial.get_json()["available_units"] == 1

    checkout = client.post(
        "/rentals",
        json={"equipment_id": equipment_id, "renter_id": renter_id},
    )
    assert checkout.status_code == 201
    rental_id = checkout.get_json()["id"]

    during = client.get(f"/equipment/{equipment_id}/availability")
    assert during.status_code == 200
    assert during.get_json() == {
        "equipment_id": equipment_id,
        "is_available": True,
        "available_units": 0,
        "total_units": 1,
    }

    returned = client.put(f"/rentals/{rental_id}/return")
    assert returned.status_code == 200

    after = client.get(f"/equipment/{equipment_id}/availability")
    assert after.status_code == 200
    assert after.get_json() == initial.get_json()


def test_status_and_availability_for_unknown_equipment_return_errors(client):
    """Unknown IDs cannot be updated or produce an availability summary."""
    updated = client.patch(
        "/equipment/999/status",
        json={"is_available": False},
    )
    assert updated.status_code == 404
    assert updated.get_json() == {"error": "Equipment not found"}

    availability = client.get("/equipment/999/availability")
    assert availability.status_code == 404
    assert availability.get_json() == {"error": "Equipment not found"}

    assert client.get("/equipment").get_json() == []