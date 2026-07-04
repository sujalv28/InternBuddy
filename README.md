# Internbuddy 🎓

An AI internship-search agent. Give it your profile and a Google Drive resume link; it scrapes Internshala and LinkedIn, ranks matches with Google Gemini, and delivers a PDF/CSV report by download and email.

## Setup

1. Python 3.11+
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in:
   - `SMTP_*` and `FROM_EMAIL` — e.g. Gmail SMTP with a 16-char app password
   - `GOOGLE_API_KEY` — optional fallback Gemini key (see BYOK below)
4. Make sure the Google Drive resume is shared as **"Anyone with the link"**.

### Bring Your Own Key (BYOK)

The app asks each user for **their own** Gemini API key in the form and uses it
to rank matches — so you never spend your own quota on other people's runs. Get
a free key at <https://aistudio.google.com/apikey>. The `.env` `GOOGLE_API_KEY`
is only used as a fallback when no key is supplied programmatically.

## Run

```bash
streamlit run internbuddy/app.py
```

## Test

```bash
python -m pytest -v
```

## Notes

- Only Internshala and the LinkedIn guest endpoint are scraped (Indeed blocks bots). Scraping is best-effort and polite (custom User-Agent + delay); a blocked source degrades gracefully and the run continues.
- Site HTML changes over time; if a scraper returns nothing, the CSS selectors in `internbuddy/scrapers.py` may need updating against the live page.
- Respect each site's Terms of Service and rate limits.
