from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from notification_service import build_return_reminder, send_notification

from app import store
from app.models.rental import Rental

# A return reminder is sent only when the rental is due within this many days
# (or is already overdue).
REMINDER_WINDOW_DAYS = 2

rentals_bp = Blueprint("rentals", __name__, url_prefix="/rentals")


@rentals_bp.route("", methods=["GET"])
def list_rentals():
    results = list(store.rentals.values())
    renter_id = request.args.get("renter_id", type=int)
    equipment_id = request.args.get("equipment_id", type=int)
    if renter_id is not None:
        results = [r for r in results if r.equipment_id == renter_id]
    if equipment_id is not None:
        results = [r for r in results if r.equipment_id == equipment_id]
    return jsonify([r.to_dict() for r in results])


@rentals_bp.route("", methods=["POST"])
def checkout_equipment():
    data = request.get_json()
    item = store.equipment.get(data["equipment_id"])
    if item is None:
        return jsonify({"error": "Equipment not found"}), 404

    # BUG: does not check item.is_available — out-of-service equipment can
    # still be checked out. The check below is intentionally absent:
    #   if not item.is_available:
    #       return jsonify({"error": "Equipment is out of service"}), 400
    item.available_units -= 1

    rental_id = store.next_id("rental")
    rental = Rental(
        id=rental_id,
        equipment_id=data["equipment_id"],
        renter_id=data["renter_id"],
        due_date=Rental.default_due_date(),
        deposit_amount=data.get("deposit_amount", 0.0),
    )
    store.rentals[rental_id] = rental
    return jsonify(rental.to_dict()), 201


@rentals_bp.route("/<int:rental_id>/return", methods=["PUT"])
def return_equipment(rental_id):
    rental = store.rentals.get(rental_id)
    if rental is None:
        return jsonify({"error": "Rental not found"}), 404
    if rental.return_date is not None:
        return jsonify({"error": "Rental already returned"}), 400

    rental.return_date = date.today()
    item = store.equipment.get(rental.equipment_id)
    if item is not None:
        item.available_units += 1

    return jsonify(rental.to_dict())


@rentals_bp.route("/<int:rental_id>/extend", methods=["PUT"])
def extend_rental(rental_id):
    """Extend a rental's due date by the given number of days."""
    rental = store.rentals.get(rental_id)
    if rental is None:
        return jsonify({"error": "Rental not found"}), 404
    if rental.return_date is not None:
        return jsonify({"error": "Rental already returned"}), 400

    data = request.get_json()
    days = data.get("days", 1)
    rental.due_date = rental.due_date + timedelta(days=days)
    return jsonify(rental.to_dict())


@rentals_bp.route("/<int:rental_id>/deposit/release", methods=["PUT"])
def release_deposit(rental_id):
    """Release the damage deposit hold for a returned rental.

    BUG: this endpoint returns {"deposit_released": true} in the response
    but does NOT persist the change on the rental object. A subsequent GET
    on the rental will still show deposit_released as false. The missing line
    is:
        rental.deposit_released = True
    """
    rental = store.rentals.get(rental_id)
    if rental is None:
        return jsonify({"error": "Rental not found"}), 404
    if rental.return_date is None:
        return jsonify({"error": "Equipment has not been returned yet"}), 400

    # BUG: rental.deposit_released is never set to True here — state is not persisted.
    return jsonify({"rental_id": rental_id, "deposit_released": True})


@rentals_bp.route("/<int:rental_id>/remind", methods=["POST"])
def send_return_reminder(rental_id):
    """Email the renter a return reminder for an active rental.

    A reminder is sent only when the rental has not been returned, has not
    already been reminded, and is due within REMINDER_WINDOW_DAYS days or is
    overdue. On success the rental is marked reminder_sent. If the
    notification service fails, the endpoint returns 503, the rental is left
    unchanged, and the reminder can be retried.
    """
    rental = store.rentals.get(rental_id)
    if rental is None:
        return jsonify({"error": "Rental not found"}), 404
    if rental.return_date is not None:
        return jsonify({"error": "Rental already returned"}), 400

    renter = store.renters.get(rental.renter_id)
    if renter is None:
        return jsonify({"error": "Renter not found"}), 404

    if rental.reminder_sent:
        return jsonify({
            "rental_id": rental_id,
            "reminder_sent": False,
            "reason": "Reminder already sent",
        })

    days_until_due = (rental.due_date - date.today()).days
    if days_until_due > REMINDER_WINDOW_DAYS:
        return jsonify({
            "rental_id": rental_id,
            "reminder_sent": False,
            "reason": f"Rental is not due within {REMINDER_WINDOW_DAYS} days",
        })

    item = store.equipment.get(rental.equipment_id)
    equipment_name = item.name if item is not None else f"equipment #{rental.equipment_id}"
    subject, message = build_return_reminder(
        renter.name, equipment_name, rental.due_date.isoformat(), days_until_due
    )

    if not send_notification(renter.email, subject, message):
        return jsonify({
            "rental_id": rental_id,
            "reminder_sent": False,
            "error": "Notification service failed; reminder not sent",
        }), 503

    rental.reminder_sent = True
    return jsonify({
        "rental_id": rental_id,
        "reminder_sent": True,
        "recipient": renter.email,
        "overdue": days_until_due < 0,
    })
