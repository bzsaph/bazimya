"""Mail.

The Mail facade on Python's smtplib — stdlib, so nothing to install.

    Mail.to('you@example.com').send(
        subject='Welcome',
        view='emails.welcome',
        data={'name': 'James'},
    )

Three drivers:
  log    writes the message to storage/logs/mail.log (the default locally,
         so development never sends real email by accident)
  smtp   a real server
  array  keeps messages in memory, for tests
"""

import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage


class MailError(RuntimeError):
    pass


class PendingMail:
    """The chainable builder returned by Mail.to(...)."""

    def __init__(self, mailer, to=None):
        self.mailer = mailer
        self._to = _as_list(to)
        self._cc = []
        self._bcc = []
        self._reply_to = None

    def to(self, *addresses):
        self._to.extend(_flatten(addresses))

        return self

    def cc(self, *addresses):
        self._cc.extend(_flatten(addresses))

        return self

    def bcc(self, *addresses):
        self._bcc.extend(_flatten(addresses))

        return self

    def reply_to(self, address):
        self._reply_to = address

        return self

    def send(self, subject="", view=None, data=None, html=None, text=None, attachments=None):
        return self.mailer.send(
            to=self._to,
            subject=subject,
            view=view,
            data=data,
            html=html,
            text=text,
            cc=self._cc,
            bcc=self._bcc,
            reply_to=self._reply_to,
            attachments=attachments,
        )


class Mailer:
    def __init__(self, config=None, application=None):
        self.config = dict(config or {})
        self.app = application
        self.sent = []

    def driver(self):
        return str(self.config.get("default", "log")).lower()

    def _mailer_config(self, driver):
        return (self.config.get("mailers", {}) or {}).get(driver, {}) or {}

    # -- building ---------------------------------------------------------

    def to(self, *addresses):
        return PendingMail(self, _flatten(addresses))

    def send(
        self,
        to,
        subject="",
        view=None,
        data=None,
        html=None,
        text=None,
        cc=None,
        bcc=None,
        reply_to=None,
        attachments=None,
    ):
        recipients = _as_list(to)

        if not recipients:
            raise MailError("An email needs at least one recipient.")

        if view is not None:
            html = self._render(view, data)

        if html is None and text is None:
            raise MailError(
                "An email needs a body: pass view=, html= or text=."
            )

        message = self._build(
            recipients, subject, html, text, cc, bcc, reply_to, attachments
        )

        driver = self.driver()

        if driver == "array":
            self.sent.append(message)

            return True

        if driver == "log":
            return self._log(message)

        if driver == "smtp":
            return self._smtp(message)

        raise MailError("Unknown mail driver [{}].".format(driver))

    def _render(self, view, data):
        from ..facades import View

        return View.render(view, data or {})

    def _build(self, to, subject, html, text, cc, bcc, reply_to, attachments):
        message = EmailMessage()

        from_address = self.config.get("from", {}) or {}
        sender = from_address.get("address", "hello@example.com")
        name = from_address.get("name")

        message["From"] = "{} <{}>".format(name, sender) if name else sender
        message["To"] = ", ".join(to)
        message["Subject"] = subject
        message["Date"] = datetime.now().astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")

        if cc:
            message["Cc"] = ", ".join(_as_list(cc))

        if reply_to:
            message["Reply-To"] = reply_to

        # Bcc is deliberately not written as a header — it is passed to the
        # server as an envelope recipient instead, which is what makes it blind.
        message._bazimya_bcc = _as_list(bcc)

        if text is not None:
            message.set_content(text)

            if html is not None:
                message.add_alternative(html, subtype="html")
        else:
            message.set_content(_strip_tags(html))
            message.add_alternative(html, subtype="html")

        for attachment in attachments or []:
            self._attach(message, attachment)

        return message

    @staticmethod
    def _attach(message, attachment):
        import mimetypes

        if isinstance(attachment, str):
            path, filename = attachment, os.path.basename(attachment)
        else:
            path, filename = attachment.get("path"), attachment.get("name")
            filename = filename or os.path.basename(path or "attachment")

        with open(path, "rb") as handle:
            payload = handle.read()

        guessed, _ = mimetypes.guess_type(filename)
        main, _, sub = (guessed or "application/octet-stream").partition("/")

        message.add_attachment(payload, maintype=main, subtype=sub, filename=filename)

    # -- drivers ----------------------------------------------------------

    def _log(self, message):
        path = self.config.get("log_path", "storage/logs/mail.log")

        if self.app is not None and not os.path.isabs(path):
            path = self.app.path(path)

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, "a", encoding="utf-8") as handle:
                handle.write("\n" + "=" * 72 + "\n")
                handle.write(message.as_string())
                handle.write("\n")

            return True
        except OSError as error:
            raise MailError("Could not write the mail log: {}".format(error)) from error

    def _smtp(self, message):
        settings = self._mailer_config("smtp")

        host = settings.get("host", "127.0.0.1")
        port = int(settings.get("port", 587) or 587)
        username = settings.get("username")
        password = settings.get("password")
        encryption = str(settings.get("encryption", "tls") or "").lower()
        timeout = int(settings.get("timeout", 30) or 30)

        recipients = _as_list(message["To"].split(", ")) + list(
            getattr(message, "_bazimya_bcc", [])
        )

        if message["Cc"]:
            recipients += message["Cc"].split(", ")

        try:
            if encryption == "ssl":
                server = smtplib.SMTP_SSL(
                    host, port, timeout=timeout, context=ssl.create_default_context()
                )
            else:
                server = smtplib.SMTP(host, port, timeout=timeout)

            with server:
                if encryption == "tls":
                    server.starttls(context=ssl.create_default_context())

                if username:
                    server.login(username, password or "")

                server.send_message(message, to_addrs=[r.strip() for r in recipients if r.strip()])

            return True
        except (smtplib.SMTPException, OSError, ssl.SSLError) as error:
            raise MailError("Could not send mail via {}:{} — {}".format(host, port, error)) from error

    # -- testing ----------------------------------------------------------

    def flush(self):
        self.sent = []

        return self


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    return list(value)


def _flatten(values):
    flat = []

    for value in values:
        flat.extend(_as_list(value))

    return flat


def _strip_tags(html):
    """A plain-text fallback, so the message is not HTML-only."""
    import re

    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)

    import html as html_module

    return re.sub(r"\n{3,}", "\n\n", html_module.unescape(text)).strip()
