import streamlit as st

from graph import run
from models import UserProfile

st.set_page_config(page_title="Internbuddy", page_icon="🎓")
st.title("Internbuddy — AI Internship Finder")
st.caption("Find internships matched to your profile, delivered as a report.")

with st.form("profile_form"):
    name = st.text_input("Name")
    stream = st.text_input("Educational stream", placeholder="e.g. B.Tech Computer Science")
    interest = st.text_input("Field of interest", placeholder="e.g. machine learning")
    email = st.text_input("Email")
    resume_link = st.text_input(
        "Google Drive resume link",
        placeholder="https://drive.google.com/file/d/.../view (shared: anyone with the link)",
    )
    gemini_api_key = st.text_input(
        "Your Gemini API key",
        type="password",
        help="Get a free key at https://aistudio.google.com/apikey — used only to rank your matches.",
    )
    report_format = st.radio("Report format", ["csv", "pdf"], horizontal=True)
    top_n = st.slider("Number of matches", min_value=5, max_value=20, value=10)
    submitted = st.form_submit_button("Find internships")

if submitted:
    profile = UserProfile(name, stream, interest, email, resume_link)
    problems = profile.validate()
    if not gemini_api_key.strip():
        problems.append("Your Gemini API key is required.")
    if problems:
        for p in problems:
            st.error(p)
        st.stop()

    with st.spinner("Searching Internshala and LinkedIn, ranking with Gemini..."):
        try:
            state = run(profile, report_format=report_format, top_n=top_n,
                        gemini_api_key=gemini_api_key.strip())
        except Exception as exc:  # config errors, unexpected failures
            st.error(f"Something went wrong: {exc}")
            st.stop()

    for warning in state.get("errors", []):
        st.warning(warning)

    matched = state.get("matched_jobs", [])
    if not matched:
        st.info("No internships matched your profile. Try a broader field of interest.")
        st.stop()

    st.success(f"Found {len(matched)} matches for {profile.name}.")
    st.dataframe(
        [
            {
                "Company": m.company,
                "Job Role": m.role,
                "Job Location": m.location,
                "Why This Role Is For You": m.why,
            }
            for m in matched
        ],
        use_container_width=True,
    )

    report_bytes = state.get("report_bytes", b"")
    if report_bytes:
        st.download_button(
            "⬇️ Download report",
            data=report_bytes,
            file_name=state.get("report_filename", "internbuddy_report"),
            mime=state.get("report_mime", "text/csv"),
        )

    email_status = state.get("email_status", "")
    if email_status == "sent":
        st.success(f"Report emailed to {profile.email}.")
    else:
        st.info(f"Email status: {email_status}")
