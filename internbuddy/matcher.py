import re

from .models import JobListing, UserProfile


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
