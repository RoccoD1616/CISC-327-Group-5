from app import store

def test_renters_form_creates_renter(client):
    response = client.post(
        "/ui/renters",
        data={
            "name": "Alex Example",
            "email": "alex@example.com",
        },
    )

    # Verify the redirect back to the renters page.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/renters")

    # Verify that exactly one renter was saved with the submitted details.
    assert len(store.renters) == 1
    renter = next(iter(store.renters.values()))
    assert renter.name == "Alex Example"
    assert renter.email == "alex@example.com"
    assert store.renters[renter.id] is renter

def test_delete_renter_form_preserves_other_renters(client):
    client.post(
        "/ui/renters",
        data={"name": "Alex Example", "email": "alex@example.com"},
    )
    client.post(
        "/ui/renters",
        data={"name": "Sam Example", "email": "sam@example.com"},
    )

    renters_by_email = {
        renter.email: renter for renter in store.renters.values()
    }
    deleted_id = renters_by_email["alex@example.com"].id
    remaining_id = renters_by_email["sam@example.com"].id

    response = client.post(f"/ui/renters/{deleted_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/renters")

    # Only the selected renter should be removed.
    assert deleted_id not in store.renters
    assert set(store.renters) == {remaining_id}
    assert store.renters[remaining_id].name == "Sam Example"
    assert store.renters[remaining_id].email == "sam@example.com"

def test_delete_unknown_renter_form_preserves_existing_renter(client):
    client.post(
        "/ui/renters",
        data={"name": "Sam Example", "email": "sam@example.com"},
    )

    assert len(store.renters) == 1
    renter = next(iter(store.renters.values()))
    unknown_id = renter.id + 1

    response = client.post(f"/ui/renters/{unknown_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/renters")

    # An unknown ID must not remove or change the existing renter.
    assert set(store.renters) == {renter.id}
    assert store.renters[renter.id].name == "Sam Example"
    assert store.renters[renter.id].email == "sam@example.com"

def test_release_deposit_unknown_rental_preserves_existing_rental(client):
    equipment_response = client.post(
        "/equipment",
        json={"name": "Test Camera", "category": "Electronics"},
    )
    renter_response = client.post(
        "/renters",
        json={"name": "Sam Example", "email": "sam@example.com"},
    )
    assert equipment_response.status_code == 201
    assert renter_response.status_code == 201

    equipment_id = equipment_response.get_json()["id"]
    rental_response = client.post(
        "/rentals",
        json={
            "equipment_id": equipment_id,
            "renter_id": renter_response.get_json()["id"],
            "deposit_amount": 100,
        },
    )
    assert rental_response.status_code == 201

    original_rental = rental_response.get_json()
    original_units = store.equipment[equipment_id].available_units
    unknown_id = original_rental["id"] + 1

    response = client.put(f"/rentals/{unknown_id}/deposit/release")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Rental not found"}

    # The failed request must leave the existing rental and inventory unchanged.
    assert set(store.rentals) == {original_rental["id"]}
    assert store.rentals[original_rental["id"]].to_dict() == original_rental
    assert store.equipment[equipment_id].available_units == original_units
