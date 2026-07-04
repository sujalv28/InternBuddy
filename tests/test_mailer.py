import mailer
from models import UserProfile

PROFILE = UserProfile("Asha", "B.Tech", "ML", "asha@example.com", "link")
SMTP_CFG = {
    "host": "smtp.example.com", "port": 587, "user": "u@example.com",
    "password": "pw", "from_email": "u@example.com",
}


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent = msg


def test_send_report_sends_message(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    status = mailer.send_report(PROFILE, b"col1,col2\n", "r.csv", "text/csv", smtp=SMTP_CFG)
    assert status == "sent"
    server = FakeSMTP.instances[0]
    assert server.started_tls is True
    assert server.logged_in == ("u@example.com", "pw")
    assert server.sent["To"] == "asha@example.com"
    assert server.sent["From"] == "u@example.com"
    # attachment present
    attachments = [p for p in server.sent.iter_attachments()]
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "r.csv"
