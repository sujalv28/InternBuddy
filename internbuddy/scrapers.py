import time

import requests
from bs4 import BeautifulSoup

from .models import JobListing

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InternbuddyBot/1.0; +https://example.com/bot)"
}
REQUEST_DELAY = 1.0


def _get(url, params=None, timeout=20) -> str:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_internshala(html: str) -> list[JobListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[JobListing] = []
    for card in soup.select("div.individual_internship"):
        role_el = card.select_one(".job-internship-name") or card.select_one(".profile")
        company_el = card.select_one(".company-name") or card.select_one(".company_name")
        if not role_el or not company_el:
            continue
        role = role_el.get_text(strip=True)
        company = company_el.get_text(strip=True)
        loc_el = card.select_one(".location_link") or card.select_one(".locations")
        location = loc_el.get_text(strip=True) if loc_el else "Not specified"

        link_el = role_el if role_el.name == "a" else role_el.select_one("a")
        href = link_el["href"] if link_el and link_el.has_attr("href") else ""
        url = href if href.startswith("http") else f"https://internshala.com{href}"

        meta = []
        for chip in card.select(".item_body, .stipend, .status-success"):
            text = chip.get_text(strip=True)
            if text:
                meta.append(text)
        description = " | ".join(dict.fromkeys(meta)) or f"{role} at {company}"

        listings.append(JobListing(company, role, location, description, url, "internshala"))
    return listings


def scrape_internshala(field_of_interest: str, max_pages: int = 1) -> list[JobListing]:
    keyword = field_of_interest.strip().lower().replace(" ", "-")
    results: list[JobListing] = []
    for page in range(1, max_pages + 1):
        url = f"https://internshala.com/internships/keywords-{keyword}/page-{page}/"
        html = _get(url)
        results.extend(parse_internshala(html))
        time.sleep(REQUEST_DELAY)
    return results
