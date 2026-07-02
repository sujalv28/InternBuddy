import io
import re

import pdfplumber
import requests
from docx import Document

_DRIVE_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]+)|[?&]id=([A-Za-z0-9_-]+)")


class ResumeError(Exception):
    """Raised when a resume cannot be fetched or parsed."""


def extract_drive_id(link: str) -> str:
    match = _DRIVE_ID_RE.search(link or "")
    if not match:
        raise ResumeError(f"Could not find a Google Drive file id in: {link!r}")
    return match.group(1) or match.group(2)


def download_resume(link: str, timeout: int = 30) -> bytes:
    file_id = extract_drive_id(link)
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def extract_text(data: bytes) -> str:
    if data[:4] == b"%PDF":
        parts = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    if data[:2] == b"PK":  # DOCX files are ZIP archives
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    return data.decode("utf-8", errors="ignore").strip()


def get_resume_text(link: str) -> str:
    return extract_text(download_resume(link))
