"""Notifications.

Laravel's notification classes, with the channels that can be built on the
standard library:

    class InvoicePaid(Notification):
        def via(self, notifiable):
            return ['mail', 'database']

        def to_mail(self, notifiable):
            return {
                'subject': 'Invoice paid',
                'view': 'emails.invoice-paid',
                'data': {'invoice': self.invoice},
            }

        def to_array(self, notifiable):
            return {'invoice_id': self.invoice.id}

    Notify.send(user, InvoicePaid(invoice))

`database` needs a notifications table:

    bazimya make:migration create_notifications_table --create=notifications
"""

import json
import uuid
from datetime import datetime


class Notification:
    """Base class. Override via() and one to_*() per channel."""

    def via(self, notifiable):
        return ["mail"]

    def to_mail(self, notifiable):
        raise NotImplementedError(
            "{} lists the mail channel but does not define to_mail().".format(
                type(self).__name__
            )
        )

    def to_array(self, notifiable):
        """The payload stored by the database channel and written to the log."""
        return {}

    def to_database(self, notifiable):
        return self.to_array(notifiable)

    def to_log(self, notifiable):
        return self.to_array(notifiable)

    def notification_type(self):
        return type(self).__name__


class NotificationSender:
    """The Notify facade. Routes a notification to its channels."""

    def __init__(self, application):
        self.app = application

    def send(self, notifiables, notification):
        """Deliver to one recipient or many. Returns a per-channel report."""
        results = []

        for notifiable in _as_list(notifiables):
            for channel in notification.via(notifiable) or []:
                results.append(self._send_one(notifiable, notification, channel))

        return results

    def send_now(self, notifiables, notification):
        # There is no queue, so this is `send`. Kept so that code written
        # against Laravel's API does not have to change.
        return self.send(notifiables, notification)

    def _send_one(self, notifiable, notification, channel):
        try:
            handler = getattr(self, "_channel_" + str(channel), None)

            if handler is None:
                return {"channel": channel, "sent": False, "error": "Unknown channel"}

            handler(notifiable, notification)

            return {"channel": channel, "sent": True}
        except Exception as error:  # noqa: BLE001 — one failing channel must
            # not stop the others; a bounced email should not lose the
            # database record.
            return {"channel": channel, "sent": False, "error": str(error)}

    # -- channels ---------------------------------------------------------

    def _channel_mail(self, notifiable, notification):
        message = notification.to_mail(notifiable)
        address = self._route(notifiable, "mail")

        if not address:
            raise ValueError(
                "{} has no email address. Give it an `email` attribute or a "
                "route_notification_for_mail() method.".format(type(notifiable).__name__)
            )

        mailer = self.app.make("mail")

        if isinstance(message, dict):
            return mailer.to(address).send(**message)

        # A pre-built PendingMail is sent as it stands.
        return message

    def _channel_database(self, notifiable, notification):
        connection = self.app.make("db")

        connection.table("notifications").insert(
            {
                "id": str(uuid.uuid4()),
                "type": notification.notification_type(),
                "notifiable_type": type(notifiable).__name__,
                "notifiable_id": notifiable.key(),
                "data": json.dumps(notification.to_database(notifiable), default=str),
                "read_at": None,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        return True

    def _channel_log(self, notifiable, notification):
        import os

        path = self.app.storage_path("logs", "notifications.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                "[{}] {} -> {}#{}: {}\n".format(
                    datetime.now().isoformat(timespec="seconds"),
                    notification.notification_type(),
                    type(notifiable).__name__,
                    notifiable.key(),
                    json.dumps(notification.to_log(notifiable), default=str),
                )
            )

        return True

    @staticmethod
    def _route(notifiable, channel):
        """Where a notification goes for this recipient.

        A model may override it with route_notification_for_mail(); otherwise
        the `email` attribute is used.
        """
        custom = getattr(notifiable, "route_notification_for_" + channel, None)

        if callable(custom):
            return custom()

        if channel == "mail":
            try:
                return notifiable.email
            except AttributeError:
                return None

        return None


def _as_list(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)

    return [value]
