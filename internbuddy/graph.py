from langgraph.graph import StateGraph, START, END

import matcher, mailer, models, report, resume, scrapers
from models import AgentState, UserProfile


def node_parse_resume(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    try:
        text = resume.get_resume_text(state["profile"].resume_link)
    except Exception as exc:
        text = ""
        errors.append(f"Resume could not be read ({exc}); using stream/interest only.")
    return {"resume_text": text, "errors": errors}


def node_scrape(state: AgentState) -> dict:
    profile: UserProfile = state["profile"]
    errors = list(state.get("errors", []))
    listings = []
    try:
        listings += scrapers.scrape_internshala(profile.field_of_interest)
    except Exception as exc:
        errors.append(f"Internshala scrape failed: {exc}")
    try:
        listings += scrapers.scrape_linkedin_guest(profile.field_of_interest)
    except Exception as exc:
        errors.append(f"LinkedIn scrape failed: {exc}")
    return {"raw_listings": listings, "errors": errors}


def node_filter(state: AgentState) -> dict:
    filtered = matcher.filter_candidates(
        state.get("raw_listings", []), state["profile"]
    )
    return {"filtered_listings": filtered}


def node_match(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    filtered = state.get("filtered_listings", [])
    if not filtered:
        return {"matched_jobs": [], "errors": errors}
    try:
        matched = matcher.match_jobs(
            state["profile"], state.get("resume_text", ""),
            filtered, state.get("top_n", 10),
            api_key=state.get("gemini_api_key"),
        )
    except Exception as exc:
        errors.append(f"Matching failed: {exc}")
        matched = matcher.fallback_matches(filtered, state["profile"],
                                           state.get("top_n", 10))
    return {"matched_jobs": matched, "errors": errors}


def node_report(state: AgentState) -> dict:
    matched = state.get("matched_jobs", [])
    if not matched:
        return {"report_bytes": b""}
    data, mime, filename = report.build_report(
        state.get("report_format", "csv"), matched, state["profile"]
    )
    return {"report_bytes": data, "report_mime": mime, "report_filename": filename}


def node_email(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    if not state.get("report_bytes"):
        return {"email_status": "skipped (no matches to send)", "errors": errors}
    try:
        mailer.send_report(
            state["profile"], state["report_bytes"],
            state["report_filename"], state["report_mime"],
        )
        status = "sent"
    except Exception as exc:
        status = f"failed: {exc}"
        errors.append(f"Email delivery failed: {exc}")
    return {"email_status": status, "errors": errors}


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_resume", node_parse_resume)
    builder.add_node("scrape", node_scrape)
    builder.add_node("filter", node_filter)
    builder.add_node("match", node_match)
    builder.add_node("generate_report", node_report)
    builder.add_node("send_email", node_email)

    builder.add_edge(START, "parse_resume")
    builder.add_edge("parse_resume", "scrape")
    builder.add_edge("scrape", "filter")
    builder.add_edge("filter", "match")
    builder.add_edge("match", "generate_report")
    builder.add_edge("generate_report", "send_email")
    builder.add_edge("send_email", END)
    return builder.compile()


def run(profile: UserProfile, report_format: str = "csv", top_n: int = 10,
        gemini_api_key: str = None) -> AgentState:
    app = build_graph()
    initial: AgentState = {
        "profile": profile,
        "report_format": report_format,
        "top_n": top_n,
        "gemini_api_key": gemini_api_key,
        "errors": [],
    }
    return app.invoke(initial)
