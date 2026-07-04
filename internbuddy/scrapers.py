import time

import requests
from bs4 import BeautifulSoup

from models import JobListing

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_DELAY = 1.0


def _get(url, params=None, timeout=20) -> str:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _safe_url(url: str) -> str:
    """Only trust absolute http(s) URLs; blank anything else (e.g. javascript:)
    so a scraped link never becomes an unsafe 'Apply Link'."""
    return url if url.startswith(("http://", "https://")) else ""


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
        if href.startswith(("http://", "https://")):
            url = href
        elif href.startswith("/"):
            url = f"https://internshala.com{href}"
        else:
            url = ""

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


def parse_linkedin(html: str) -> list[JobListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[JobListing] = []
    for card in soup.select("li"):
        role_el = card.select_one("h3.base-search-card__title")
        company_el = card.select_one("h4.base-search-card__subtitle")
        if not role_el or not company_el:
            continue
        role = role_el.get_text(strip=True)
        company = company_el.get_text(strip=True)
        loc_el = card.select_one(".job-search-card__location")
        location = loc_el.get_text(strip=True) if loc_el else "Not specified"
        link_el = card.select_one("a.base-card__full-link") or card.select_one("a")
        url = ""
        if link_el and link_el.has_attr("href"):
            url = _safe_url(link_el["href"].split("?")[0])
        description = (
            f"{role} at {company} in {location}. "
            f"View the full description on LinkedIn: {url}"
        )
        listings.append(JobListing(company, role, location, description, url, "linkedin"))
    return listings


def scrape_linkedin_guest(field_of_interest: str, location: str = "India",
                          start: int = 0) -> list[JobListing]:
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {"keywords": field_of_interest, "location": location, "start": start}
    html = _get(url, params=params)
    time.sleep(REQUEST_DELAY)
    return parse_linkedin(html)
