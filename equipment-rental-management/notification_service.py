"""Notification simulator Assignment 3.

Customized for Equipment Rental Management (Group 5):
    * SENDER_NAME and SUBJECT_PREFIX brand every rental notification.
    * build_return_reminder() is the message template for the chosen event,
      a return reminder for a rental that is due soon or overdue.
    * send_notification() also fails (returns False, records nothing) when
      the recipient has no "@", simulating an undeliverable renter address.
The function name, parameters and True/False return value are unchanged.

Place this file beside run.py in your selected project folder, then use
``import notification_service`` from application code.

This module does not send real emails or make network calls. Successful
notifications are stored in memory and disappear when Python exits. It is
a teaching simulator for a single process, not a production delivery system.
The application decides when to notify someone and how to handle failure.

Examples of recipients in the supplied templates:
    Library:          member.email
    Equipment rental: renter.email
    Inventory:        supplier.contact_email or a chosen staff address

For application tests, stub send_notification to return True or False, or
mock it to verify the recipient, subject, and message. Assert the resulting
application behavior too. Patch the dependency where your application uses it.
Use clear_notifications before and after tests that use the real simulator.
"""

SENDER_NAME = "Group 5 Equipment Rental"
SUBJECT_PREFIX = "[Equipment Rental]"

_notifications = []


def build_return_reminder(renter_name: str, equipment_name: str,
                          due_date: str, days_until_due: int) -> tuple:
    """Return (subject, message) for a rental return reminder.

    days_until_due is negative when the rental is overdue, 0 when it is due
    today, and positive when it is due in the future.
    """
    if days_until_due < 0:
        days_late = -days_until_due
        unit = "day" if days_late == 1 else "days"
        subject = f"{SUBJECT_PREFIX} Overdue: please return {equipment_name}"
        message = (f"Hi {renter_name}, your rental of {equipment_name} was due "
                   f"on {due_date} and is now {days_late} {unit} overdue. "
                   f"Please return it as soon as possible. - {SENDER_NAME}")
    else:
        if days_until_due == 0:
            when = "today"
        elif days_until_due == 1:
            when = "in 1 day"
        else:
            when = f"in {days_until_due} days"
        subject = (f"{SUBJECT_PREFIX} Return reminder: {equipment_name} "
                   f"due {due_date}")
        message = (f"Hi {renter_name}, your rental of {equipment_name} is due "
                   f"back on {due_date} ({when}). Please return it on time. "
                   f"- {SENDER_NAME}")
    return subject, message


def is_service_available() -> bool:
    """Return True for this local simulator.

    Tests may stub this function to return False to simulate an outage.
    No external service is contacted and no random failures are introduced.
    """
    return True


def send_notification(recipient: str, subject: str, message: str) -> bool:
    """Record a simulated notification and return True on success.

    Return False without recording anything if any argument is not a string,
    is empty/whitespace-only, the recipient has no "@" (customization: an
    undeliverable renter address), or the simulated service is unavailable.
    This simulator does not check actual deliverability.
    Valid values are stored exactly as supplied. Repeated sends are recorded
    separately. True means recorded by the simulator, not delivered by email.
    """
    if not all(isinstance(value, str) and value.strip()
               for value in (recipient, subject, message)):
        return False

    if "@" not in recipient:
        return False

    if not is_service_available():
        return False

    _notifications.append({
        "recipient": recipient,
        "subject": subject,
        "message": message,
    })
    return True


def get_notifications() -> list:
    """Return all recorded notifications in sending order.

    Return copies of the records so callers cannot modify the stored history.
    Each record has recipient, subject, and message string fields.
    """
    return [notification.copy() for notification in _notifications]


def clear_notifications() -> None:
    """Remove all recorded notifications, for example between test cases."""
    _notifications.clear()
