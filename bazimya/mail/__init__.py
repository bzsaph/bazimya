"""Mail."""

from .mailer import Mailer, MailError, PendingMail

__all__ = ["MailError", "Mailer", "PendingMail"]
