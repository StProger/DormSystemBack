import smtplib
from email.message import EmailMessage
from .config import get_settings

settings = get_settings()

def send_email_html(to_email: str, subject: str, html: str):
    """
    Минимальная SMTP-отправка HTML.
    Нужны настройки в .env:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
      SMTP_TLS=true/false
    """
    host = getattr(settings, "SMTP_HOST", None)
    port = getattr(settings, "SMTP_PORT", None)
    user = getattr(settings, "SMTP_USER", None)
    password = getattr(settings, "SMTP_PASSWORD", None)
    from_email = getattr(settings, "SMTP_FROM", user)

    if not host or not port or not user or not password or not from_email:
        raise RuntimeError("SMTP settings are not configured")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("Ваш почтовый клиент не поддерживает HTML.")
    msg.add_alternative(html, subtype="html")

    use_tls = bool(getattr(settings, "SMTP_TLS", True))

    if use_tls:
        with smtplib.SMTP(host, int(port)) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, int(port)) as s:
            s.login(user, password)
            s.send_message(msg)
