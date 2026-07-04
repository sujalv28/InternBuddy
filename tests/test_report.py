import csv
import io

import report
from models import MatchedJob, UserProfile

PROFILE = UserProfile("Asha", "B.Tech", "ML", "a@x.com", "link")
MATCHED = [
    MatchedJob("Acme", "ML Intern", "Remote", "deep learning role",
               "http://a", "internshala", "http://a", "You love ML.", 1),
    MatchedJob("Beta", "Data Intern", "Pune", "sql work",
               "http://b", "linkedin", "http://b", "Great growth.", 2),
]


def test_build_csv_headers_and_rows():
    data = report.build_csv(MATCHED)
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert rows[0] == ["Company", "Job Role", "Job Location",
                       "Job Description", "Apply Link", "Why This Role Is For You"]
    assert rows[1][0] == "Acme"
    assert rows[1][4] == "http://a"
    assert rows[1][5] == "You love ML."
    assert len(rows) == 3  # header + 2


def test_build_pdf_returns_pdf_bytes():
    data = report.build_pdf(MATCHED, PROFILE)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_build_report_csv_dispatch():
    data, mime, filename = report.build_report("csv", MATCHED, PROFILE)
    assert mime == "text/csv"
    assert filename.endswith(".csv")
    assert data[:7] == b"Company"


def test_build_report_pdf_dispatch():
    data, mime, filename = report.build_report("pdf", MATCHED, PROFILE)
    assert mime == "application/pdf"
    assert filename.endswith(".pdf")
    assert data[:4] == b"%PDF"


def test_build_csv_neutralizes_formula_injection():
    evil = [MatchedJob("=cmd()", "+2+3", "-9", "@SUM(A1)", "http://a",
                       "internshala", "http://a", "=HYPERLINK(0)", 1)]
    rows = list(csv.reader(io.StringIO(report.build_csv(evil).decode("utf-8"))))
    assert rows[1][0] == "'=cmd()"
    assert rows[1][1] == "'+2+3"
    assert rows[1][3] == "'@SUM(A1)"
    assert rows[1][5] == "'=HYPERLINK(0)"


def test_build_pdf_handles_non_latin_text():
    matched = [MatchedJob("Café", "Rôle", "Zürich", "naïve résumé",
                          "http://c", "linkedin", "http://c", "Perfect — go for it! ★", 1)]
    data = report.build_pdf(matched, PROFILE)
    assert data[:4] == b"%PDF"
