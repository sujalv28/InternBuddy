from dataclasses import dataclass
from typing import TypedDict


@dataclass
class UserProfile:
    name: str
    stream: str
    field_of_interest: str
    email: str
    resume_link: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("Name is required.")
        if not self.stream.strip():
            errors.append("Educational stream is required.")
        if not self.field_of_interest.strip():
            errors.append("Field of interest is required.")
        if "@" not in self.email or "." not in self.email:
            errors.append("A valid email is required.")
        if not self.resume_link.strip():
            errors.append("Resume link is required.")
        return errors


@dataclass
class JobListing:
    company: str
    role: str
    location: str
    description: str
    url: str
    source: str


@dataclass
class MatchedJob:
    company: str
    role: str
    location: str
    description: str
    url: str
    source: str
    apply_link: str
    why: str
    rank: int


class AgentState(TypedDict, total=False):
    profile: UserProfile
    resume_text: str
    raw_listings: list
    filtered_listings: list
    matched_jobs: list
    reports: list
    report_bytes: bytes
    report_mime: str
    report_filename: str
    report_format: str
    top_n: int
    gemini_api_key: str
    email_status: str
    errors: list
