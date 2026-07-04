import csv
import io

from fpdf import FPDF

from models import UserProfile

COLUMNS = ["Company", "Job Role", "Job Location", "Job Description",
           "Apply Link", "Why This Role Is For You"]


def _latin1(text: str) -> str:
    """fpdf2 core fonts are latin-1 only; drop unencodable characters."""
    return (text or "").encode("latin-1", errors="replace").decode("latin-1")


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value) -> str:
    """Neutralize CSV formula injection: scraped text opened in Excel/Sheets
    would execute a cell that starts with =, +, -, @, TAB or CR. Prefix such
    cells with an apostrophe so spreadsheets render them as literal text."""
    text = str(value or "")
    return "'" + text if text[:1] in _FORMULA_PREFIXES else text


def build_csv(matched: list) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COLUMNS)
    for job in matched:
        writer.writerow([_csv_safe(job.company), _csv_safe(job.role),
                         _csv_safe(job.location), _csv_safe(job.description),
                         _csv_safe(job.apply_link), _csv_safe(job.why)])
    return buf.getvalue().encode("utf-8")


def build_pdf(matched: list, profile: UserProfile) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Internbuddy - Internship Matches", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, _latin1(f"Prepared for {profile.name}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    for job in matched:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, _latin1(f"{job.rank}. {job.role} - {job.company}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, _latin1(f"Location: {job.location}"), new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 6, _latin1(f"Description: {job.description}"), new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 6, _latin1(f"Apply Link: {job.apply_link}"), new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 6, _latin1(f"Why this role is for you: {job.why}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    out = pdf.output()
    return bytes(out)


def build_report(fmt: str, matched: list, profile: UserProfile) -> tuple:
    if fmt == "pdf":
        return build_pdf(matched, profile), "application/pdf", "internbuddy_report.pdf"
    return build_csv(matched), "text/csv", "internbuddy_report.csv"
