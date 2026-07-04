import smtplib
from email.message import EmailMessage

from config import get_smtp_config
from models import UserProfile


def send_report(profile: UserProfile, report_bytes: bytes, filename: str,
                mime: str, smtp: dict = None) -> str:
    cfg = smtp or get_smtp_config()

    msg = EmailMessage()
    msg["Subject"] = "Your Internbuddy internship matches"
    msg["From"] = cfg["from_email"]
    msg["To"] = profile.email
    msg.set_content(
        f"Hi {profile.name},\n\n"
        "Attached are your personalized internship matches from Internbuddy.\n\n"
        "Good luck!\n- Internbuddy"
    )

    maintype, subtype = mime.split("/", 1)
    msg.add_attachment(report_bytes, maintype=maintype, subtype=subtype,
                       filename=filename)

    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    return "sent"
