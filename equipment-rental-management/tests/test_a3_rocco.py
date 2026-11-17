from app import store
from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import patch

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

SEND_TARGET = "app.routes.rentals.send_notification"

def create_reminder_rental(client, due_in_days=1):
    """Create an active rental with a controlled due date."""
    equipment_response = client.post(
        "/equipment",
        json={
            "name": "Test Camera",
            "category": "Electronics",
            "total_units": 2,
        },
    )
    renter_response = client.post(
        "/renters",
        json={"name": "Sam Example", "email": "sam@example.com"},
    )
    assert equipment_response.status_code == 201
    assert renter_response.status_code == 201

    equipment_id = equipment_response.get_json()["id"]
    renter_id = renter_response.get_json()["id"]

    rental_response = client.post(
        "/rentals",
        json={
            "equipment_id": equipment_id,
            "renter_id": renter_id,
            "deposit_amount": 100,
        },
    )
    assert rental_response.status_code == 201

    rental_id = rental_response.get_json()["id"]
    store.rentals[rental_id].due_date = (
        date.today() + timedelta(days=due_in_days)
    )
    return rental_id, equipment_id, renter_id


def reminder_state():
    """Snapshot rental records and inventory to detect unintended changes."""
    return deepcopy({
        "rentals": {
            rental_id: rental.to_dict()
            for rental_id, rental in store.rentals.items()
        },
        "available_units": {
            equipment_id: equipment.available_units
            for equipment_id, equipment in store.equipment.items()
        },
    })


def test_reminder_failure_preserves_rental_and_inventory(client, monkeypatch):
    rental_id, _, _ = create_reminder_rental(client)
    before = reminder_state()

    # Stub: force failure without checking interactions.
    monkeypatch.setattr(
        SEND_TARGET,
        lambda recipient, subject, message: False,
    )

    response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 503
    assert response.get_json() == {
        "rental_id": rental_id,
        "reminder_sent": False,
        "error": "Notification service failed; reminder not sent",
    }
    assert store.rentals[rental_id].reminder_sent is False
    assert reminder_state() == before


def test_reminder_not_due_does_not_send(client):
    # Three days is just outside the two-day reminder window.
    rental_id, _, _ = create_reminder_rental(client, due_in_days=3)
    before = reminder_state()

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["reminder_sent"] is False
    mock_send.assert_not_called()
    assert reminder_state() == before


def test_reminder_already_sent_does_not_send_again(client):
    rental_id, _, _ = create_reminder_rental(client)
    store.rentals[rental_id].reminder_sent = True
    before = reminder_state()

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["reminder_sent"] is False
    assert response.get_json()["reason"] == "Reminder already sent"
    mock_send.assert_not_called()

    # The response means no NEW reminder was sent; the saved flag stays True.
    assert store.rentals[rental_id].reminder_sent is True
    assert reminder_state() == before


def test_reminder_returned_rental_does_not_send(client):
    rental_id, _, _ = create_reminder_rental(client)

    # Return the rental through the web route before requesting a reminder.
    return_response = client.post(f"/ui/rentals/{rental_id}/return")
    assert return_response.status_code == 302
    assert store.rentals[rental_id].return_date == date.today()
    before = reminder_state()

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Rental already returned"}
    mock_send.assert_not_called()
    assert reminder_state() == before


def test_reminder_unknown_rental_does_not_send(client):
    rental_id, _, _ = create_reminder_rental(client)
    unknown_id = rental_id + 1
    assert unknown_id not in store.rentals
    before = reminder_state()

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{unknown_id}/remind")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Rental not found"}
    mock_send.assert_not_called()
    assert reminder_state() == before


def test_reminder_missing_renter_does_not_send(client):
    rental_id, _, renter_id = create_reminder_rental(client)

    # Simulate a renter record removed while the rental remains active.
    del store.renters[renter_id]
    before = reminder_state()

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Renter not found"}
    mock_send.assert_not_called()
    assert reminder_state() == before
