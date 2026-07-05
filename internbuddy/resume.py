import io
import re

import pdfplumber
import requests
from bs4 import BeautifulSoup
from docx import Document

_DRIVE_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]+)|[?&]id=([A-Za-z0-9_-]+)")


class ResumeError(Exception):
    """Raised when a resume cannot be fetched or parsed."""


def extract_drive_id(link: str) -> str:
    match = _DRIVE_ID_RE.search(link or "")
    if not match:
        raise ResumeError(f"Could not find a Google Drive file id in: {link!r}")
    return match.group(1) or match.group(2)


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def download_resume(link: str, timeout: int = 30) -> bytes:
    file_id = extract_drive_id(link)
    session = requests.Session()
    session.headers["User-Agent"] = _BROWSER_UA

    # An uploaded PDF/DOCX downloads from the uc endpoint. A native Google Doc
    # 500s there and must be exported as PDF instead, so try that as a fallback.
    data = _download_upload(session, file_id, timeout)
    if data is None:
        data = _export_google_doc(session, file_id, timeout)
    if data is None:
        raise ResumeError(
            "Could not download the resume. Make sure the Drive link is shared "
            "with 'Anyone with the link'."
        )
    return data


def _download_upload(session, file_id: str, timeout: int):
    """Fetch an uploaded file (PDF/DOCX) via the uc endpoint, following the
    virus-scan confirm form for large files. Returns bytes on success, or None
    if this isn't a downloadable upload (e.g. a native Google Doc, which 500s)."""
    try:
        resp = session.get("https://drive.google.com/uc", timeout=timeout,
                           params={"id": file_id, "export": "download"})
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    # Small files return raw bytes; large/scanned files return an HTML confirm
    # form we follow with the exact fields Google supplies.
    if "text/html" not in resp.headers.get("Content-Type", "").lower():
        return resp.content
    action, fields = _parse_confirm_form(resp.text)
    if not action:
        return None
    resp = session.get(action, params=fields, timeout=timeout)
    return resp.content if resp.status_code == 200 else None


def _export_google_doc(session, file_id: str, timeout: int):
    """Export a native Google Doc as PDF. Returns bytes on success, or None."""
    try:
        resp = session.get(
            f"https://docs.google.com/document/d/{file_id}/export",
            params={"format": "pdf"}, timeout=timeout)
    except requests.RequestException:
        return None
    if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
        return resp.content
    return None


def _parse_confirm_form(html: str) -> tuple[str, dict]:
    """Extract the download confirmation form's action URL and hidden fields
    from Google Drive's virus-scan interstitial page."""
    form = BeautifulSoup(html, "html.parser").find("form")
    if not form:
        return "", {}
    fields = {inp["name"]: inp.get("value", "")
              for inp in form.select("input[name]")}
    return form.get("action", ""), fields


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
