import io

import pytest
from docx import Document
from fpdf import FPDF

import resume


def test_extract_drive_id_file_form():
    link = "https://drive.google.com/file/d/1A2B3C_dEF/view?usp=sharing"
    assert resume.extract_drive_id(link) == "1A2B3C_dEF"


def test_extract_drive_id_open_form():
    link = "https://drive.google.com/open?id=XyZ-123"
    assert resume.extract_drive_id(link) == "XyZ-123"


def test_extract_drive_id_invalid():
    with pytest.raises(resume.ResumeError):
        resume.extract_drive_id("https://example.com/nope")


def test_extract_text_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Skilled in Python and machine learning")
    data = bytes(pdf.output())
    text = resume.extract_text(data)
    assert "Python" in text


def test_extract_text_docx():
    doc = Document()
    doc.add_paragraph("Experienced in data science and SQL")
    buf = io.BytesIO()
    doc.save(buf)
    text = resume.extract_text(buf.getvalue())
    assert "data science" in text


def test_get_resume_text_uses_download(monkeypatch):
    doc = Document()
    doc.add_paragraph("hello resume")
    buf = io.BytesIO()
    doc.save(buf)
    monkeypatch.setattr(resume, "download_resume", lambda link, timeout=30: buf.getvalue())
    assert "hello resume" in resume.get_resume_text("https://drive.google.com/file/d/ID/view")
