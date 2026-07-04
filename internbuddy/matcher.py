import json
import re

from models import JobListing, MatchedJob, UserProfile


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def filter_candidates(listings: list, profile: UserProfile, limit: int = 25) -> list:
    seen = set()
    deduped: list = []
    for job in listings:
        key = (job.company.strip().lower(), job.role.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    interest = _tokens(f"{profile.field_of_interest} {profile.stream}")

    def score(job: JobListing) -> int:
        return len(interest & _tokens(f"{job.role} {job.description}"))

    ranked = sorted(deduped, key=score, reverse=True)
    return ranked[:limit]


_MODEL_NAME = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """You are an expert internship matching assistant.

Candidate profile:
- Name: {name}
- Educational stream: {stream}
- Field of interest: {interest}

Candidate resume (may be empty):
\"\"\"{resume}\"\"\"

Below are internship listings as a numbered list (index: role @ company - description).
Pick the best matches for this candidate, ranked best first, at most {top_n} items.
For each, write a 2-3 sentence "why this role is for you" grounded in the
candidate's stream, interest, and resume.

Listings:
{listings}

Return ONLY valid JSON, no prose, in exactly this shape:
{{"matches": [{{"index": <int>, "why": "<text>"}}]}}
"""


def _default_client(api_key: str = None):
    from google import genai

    from config import get_google_api_key

    if api_key is None:
        client = genai.Client(api_key=get_google_api_key())
    else:
        client = genai.Client(api_key=api_key)

    class _GeminiAdapter:
        """Adapts the google-genai client to a .generate_content(prompt) -> obj-with-.text interface."""

        def generate_content(self, prompt):
            return client.models.generate_content(model=_MODEL_NAME, contents=prompt)

    return _GeminiAdapter()


def _format_listings(listings: list) -> str:
    lines = []
    for i, job in enumerate(listings):
        lines.append(f"{i}: {job.role} @ {job.company} - {job.description[:200]}")
    return "\n".join(lines)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start:end + 1])


def fallback_matches(listings: list, profile: UserProfile, top_n: int = 10) -> list:
    out = []
    for rank, job in enumerate(listings[:top_n], start=1):
        why = (
            f"This {job.role} position aligns with your interest in "
            f"{profile.field_of_interest} and your {profile.stream} background, "
            f"offering hands-on experience at {job.company}."
        )
        out.append(MatchedJob(job.company, job.role, job.location, job.description,
                              job.url, job.source, job.url, why, rank))
    return out


def match_jobs(profile: UserProfile, resume_text: str, listings: list,
               top_n: int = 10, client=None, api_key=None) -> list:
    if not listings:
        return []
    model = client or _default_client(api_key)
    prompt = _PROMPT_TEMPLATE.format(
        name=profile.name,
        stream=profile.stream,
        interest=profile.field_of_interest,
        resume=(resume_text or "")[:4000],
        top_n=top_n,
        listings=_format_listings(listings),
    )
    try:
        resp = model.generate_content(prompt)
        data = _parse_json(resp.text)
        matches = []
        for rank, item in enumerate(data.get("matches", [])[:top_n], start=1):
            idx = int(item["index"])
            if 0 <= idx < len(listings):
                job = listings[idx]
                matches.append(MatchedJob(job.company, job.role, job.location,
                                          job.description, job.url, job.source,
                                          job.url, str(item.get("why", "")), rank))
        if not matches:
            raise ValueError("Model returned no valid matches")
        return matches
    except Exception:
        return fallback_matches(listings, profile, top_n)
