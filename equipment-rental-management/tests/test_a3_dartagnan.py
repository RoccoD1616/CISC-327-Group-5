"""Assignment 3 tests - Member A (D'Artagnan Passailaigue).

Part 1: notification success path for POST /rentals/<id>/remind.
    send_notification is replaced where the application uses it,
    app.routes.rentals.send_notification, so no notification is recorded.
    Stub tests force a return value and check the response and state.
    Mock tests also verify the recipient, subject and message.
Part 2: coverage-directed tests for the HTML rentals pages in
    app/routes/views.py (rentals_page POST and return_rental_page), the
    uncovered areas assigned to Member A in Table A.
"""
from datetime import date, timedelta
from unittest.mock import patch

import notification_service
from app import store

SEND_TARGET = "app.routes.rentals.send_notification"


# ---------------------------------------------------------------- helpers

def create_rental(client, *, due_in_days, renter_name="Jane Doe",
                  email="jane@example.com", equipment_name="Cordless Drill"):
    """Create equipment, a renter and an active rental due in N days."""
    equipment = client.post("/equipment", json={
        "name": equipment_name, "category": "Tools", "total_units": 2,
    }).get_json()
    renter = client.post("/renters", json={
        "name": renter_name, "email": email,
    }).get_json()
    rental = client.post("/rentals", json={
        "equipment_id": equipment["id"], "renter_id": renter["id"],
    }).get_json()
    due = date.today() + timedelta(days=due_in_days)
    # Arrange: the API always sets a 7-day due date, so set it directly.
    store.rentals[rental["id"]].due_date = due
    return rental["id"], equipment["id"], due


def rental_record(client, rental_id):
    return next(r for r in client.get("/rentals").get_json()
                if r["id"] == rental_id)


# ------------------------------------------- Part 1: notification tests

def test_reminder_success_marks_rental_reminded(client, monkeypatch):
    """Stub returns True: response reports success and state is persisted."""
    monkeypatch.setattr(SEND_TARGET,
                        lambda recipient, subject, message: True)  # stub
    rental_id, equipment_id, _ = create_rental(client, due_in_days=1)

    response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json() == {
        "rental_id": rental_id,
        "reminder_sent": True,
        "recipient": "jane@example.com",
        "overdue": False,
    }
    record = rental_record(client, rental_id)
    assert record["reminder_sent"] is True
    assert record["return_date"] is None  # rental is still active
    # Sending a reminder does not touch inventory.
    equipment = client.get(f"/equipment/{equipment_id}").get_json()
    assert equipment["available_units"] == 1


def test_reminder_sends_expected_recipient_subject_and_message(client):
    """Mock verifies the exact call for a rental due tomorrow."""
    rental_id, _, due = create_rental(client, due_in_days=1)

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["reminder_sent"] is True
    mock_send.assert_called_once_with(
        "jane@example.com",
        f"[Equipment Rental] Return reminder: Cordless Drill due {due.isoformat()}",
        f"Hi Jane Doe, your rental of Cordless Drill is due back on "
        f"{due.isoformat()} (in 1 day). Please return it on time. "
        f"- Group 5 Equipment Rental",
    )
    assert rental_record(client, rental_id)["reminder_sent"] is True


def test_overdue_reminder_sent_with_overdue_wording(client):
    """Mock verifies the overdue template and the overdue flag."""
    rental_id, _, due = create_rental(client, due_in_days=-3,
                                      renter_name="Sam Lee",
                                      email="sam@example.com",
                                      equipment_name="Pressure Washer")

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["overdue"] is True
    mock_send.assert_called_once_with(
        "sam@example.com",
        "[Equipment Rental] Overdue: please return Pressure Washer",
        f"Hi Sam Lee, your rental of Pressure Washer was due on "
        f"{due.isoformat()} and is now 3 days overdue. Please return it "
        f"as soon as possible. - Group 5 Equipment Rental",
    )
    assert rental_record(client, rental_id)["reminder_sent"] is True


def test_reminder_sent_on_due_date(client):
    """Boundary: due today (0 days) is inside the window."""
    rental_id, _, due = create_rental(client, due_in_days=0)

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["overdue"] is False
    mock_send.assert_called_once()
    recipient, subject, message = mock_send.call_args.args
    assert recipient == "jane@example.com"
    assert subject.endswith(f"due {due.isoformat()}")
    assert "(today)" in message
    assert rental_record(client, rental_id)["reminder_sent"] is True


def test_reminder_sent_at_edge_of_window(client):
    """Boundary: due in exactly REMINDER_WINDOW_DAYS (2) days still sends."""
    rental_id, _, _ = create_rental(client, due_in_days=2)

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["reminder_sent"] is True
    mock_send.assert_called_once()
    assert "(in 2 days)" in mock_send.call_args.args[2]


def test_reminder_names_equipment_by_id_after_equipment_deleted(client):
    """The reminder still goes out if the equipment record was deleted."""
    rental_id, equipment_id, _ = create_rental(client, due_in_days=1)
    assert client.delete(f"/equipment/{equipment_id}").status_code == 204

    with patch(SEND_TARGET, return_value=True) as mock_send:
        response = client.post(f"/rentals/{rental_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["reminder_sent"] is True
    _, subject, message = mock_send.call_args.args
    assert f"equipment #{equipment_id}" in subject
    assert f"your rental of equipment #{equipment_id}" in message


def test_reminder_recorded_by_real_simulator(client):
    """No test double: the customized simulator records the reminder."""
    notification_service.clear_notifications()
    try:
        rental_id, _, _ = create_rental(client, due_in_days=1)

        response = client.post(f"/rentals/{rental_id}/remind")

        assert response.status_code == 200
        assert response.get_json()["reminder_sent"] is True
        sent = notification_service.get_notifications()
        assert len(sent) == 1
        assert sent[0]["recipient"] == "jane@example.com"
        assert sent[0]["subject"].startswith("[Equipment Rental] Return reminder")
    finally:
        notification_service.clear_notifications()


# ---------------------------------- Part 2: coverage-directed (views.py)

def test_rentals_form_checkout_creates_rental_and_reduces_units(client):
    equipment = client.post("/equipment", json={
        "name": "Ladder", "category": "Tools", "total_units": 3,
    }).get_json()
    renter = client.post("/renters", json={
        "name": "Ana Cruz", "email": "ana@example.com",
    }).get_json()

    response = client.post("/ui/rentals", data={
        "equipment_id": str(equipment["id"]),
        "renter_id": str(renter["id"]),
    })

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/rentals")
    rentals = client.get("/rentals").get_json()
    assert len(rentals) == 1
    assert rentals[0]["equipment_id"] == equipment["id"]
    assert rentals[0]["renter_id"] == renter["id"]
    assert rentals[0]["return_date"] is None
    assert rentals[0]["due_date"] == (date.today() + timedelta(days=7)).isoformat()
    after = client.get(f"/equipment/{equipment['id']}").get_json()
    assert after["available_units"] == 2
    page = client.get("/ui/rentals").get_data(as_text=True)
    assert "Return</button>" in page


def test_rentals_form_unknown_equipment_creates_no_rental(client):
    renter = client.post("/renters", json={
        "name": "Ana Cruz", "email": "ana@example.com",
    }).get_json()

    response = client.post("/ui/rentals", data={
        "equipment_id": "999", "renter_id": str(renter["id"]),
    })

    assert response.status_code == 302
    assert client.get("/rentals").get_json() == []
    assert store.rentals == {}


def test_rentals_page_return_marks_returned_and_restores_units(client):
    rental_id, equipment_id, _ = create_rental(client, due_in_days=5)

    response = client.post(f"/ui/rentals/{rental_id}/return")

    assert response.status_code == 302
    record = rental_record(client, rental_id)
    assert record["return_date"] == date.today().isoformat()
    equipment = client.get(f"/equipment/{equipment_id}").get_json()
    assert equipment["available_units"] == equipment["total_units"] == 2
    page = client.get("/ui/rentals").get_data(as_text=True)
    assert "Return</button>" not in page


def test_rentals_page_return_twice_does_not_double_count_units(client):
    rental_id, equipment_id, _ = create_rental(client, due_in_days=5)
    client.post(f"/ui/rentals/{rental_id}/return")

    response = client.post(f"/ui/rentals/{rental_id}/return")

    assert response.status_code == 302
    equipment = client.get(f"/equipment/{equipment_id}").get_json()
    assert equipment["available_units"] == 2  # not 3
    assert rental_record(client, rental_id)["return_date"] == date.today().isoformat()


def test_rentals_page_return_unknown_rental_changes_nothing(client):
    rental_id, equipment_id, _ = create_rental(client, due_in_days=5)

    response = client.post("/ui/rentals/999/return")

    assert response.status_code == 302
    assert rental_record(client, rental_id)["return_date"] is None
    equipment = client.get(f"/equipment/{equipment_id}").get_json()
    assert equipment["available_units"] == 1
