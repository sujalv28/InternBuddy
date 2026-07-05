# Internbuddy

An AI internship-search agent. Give it your profile and a Google Drive resume
link; it reads your resume, gathers internship listings from **Internshala**,
the **LinkedIn** guest endpoint, and a **keyless public jobs API**, ranks the
matches against your profile with **Google Gemini**, and delivers a report — as
**CSV, PDF, or both** — by download button and email. Every listing in the
report includes a direct **apply link**.

## Try it online

A hosted version runs on Streamlit Community Cloud:
**<https://internbuddy.streamlit.app>** — no install required. (You'll still
need your own Gemini key; see BYOK below.)

## How it works

A LangGraph pipeline runs one node per stage, and each stage catches its own
failures and degrades gracefully instead of crashing the run:

```
parse_resume → scrape → filter → match → generate_report → send_email
```

- **parse_resume** — downloads the resume from the Drive link and extracts text.
  Handles both **uploaded files** (PDF via `pdfplumber`, DOCX via `python-docx`)
  and **native Google Docs** (exported as PDF). A bad link falls back to
  stream/interest-only matching.
- **scrape** — pulls listings from Internshala, LinkedIn (guest), and a public
  jobs API. A blocked source is skipped; the others still return results.
- **filter** — dedupes by `(company, role)` and keyword-ranks against your
  profile, capping candidates to bound Gemini cost.
- **match** — Gemini ranks the shortlist and writes a personalized "why this
  role is for you" for each. If Gemini is unavailable, a keyword-ordered
  fallback with template text is used instead.
- **generate_report** — builds the CSV and/or PDF with columns: Company, Job
  Role, Job Location, Job Description, **Apply Link**, Why This Role Is For You.
- **send_email** — emails the report(s) over SMTP. A failed send still leaves
  the download button working.

## Setup

1. Python 3.11+
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in:
   - `SMTP_*` and `FROM_EMAIL` — e.g. Gmail SMTP with a 16-char **app password**
     (requires 2-Step Verification; `SMTP_USER` and `FROM_EMAIL` should match).
   - `GOOGLE_API_KEY` — optional fallback Gemini key (see BYOK below).
4. Make sure the Google Drive resume is shared as **"Anyone with the link"**.

### Bring Your Own Key (BYOK)

The app asks each user for **their own** Gemini API key in the form and uses it
to rank matches — so you never spend your own quota on other people's runs. Get
a free key at <https://aistudio.google.com/apikey>. The `.env` `GOOGLE_API_KEY`
is only used as a fallback when no key is supplied.

## Run

```bash
streamlit run internbuddy/app.py
```

Fill in your name, educational stream, field of interest, email, Drive resume
link, and Gemini key; choose a report format (**csv / pdf / both**) and how many
matches you want; then submit.

## Test

```bash
python -m pytest -v
```

45 tests. Scrapers are tested against saved HTML/JSON fixtures (never live
network); Gemini is tested via a fake client; the end-to-end graph test mocks
all network, Gemini, and SMTP calls.

## Deploying to Streamlit Cloud

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`, and
(optionally) `GOOGLE_API_KEY` in the app's **Secrets** — the app mirrors them
into the environment automatically, so no `.env` is needed.

## Notes

- **Internshala on cloud hosts:** datacenter IPs (including Streamlit Cloud) are
  often bot-blocked by Internshala, which can surface as a redirect error. This
  is environmental, not a bug — the LinkedIn and public-jobs sources keep results
  flowing so you still get your requested number of listings. Running locally
  from a residential IP typically reaches Internshala fine.
- Scraping is best-effort and polite (custom User-Agent + delay). Site HTML
  changes over time; if a scraper returns nothing, the CSS selectors in
  `internbuddy/scrapers.py` may need updating against the live page.
- Respect each site's Terms of Service and rate limits.
