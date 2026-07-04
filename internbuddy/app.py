import os

import streamlit as st

from graph import run
from models import UserProfile

# On Streamlit Cloud there is no .env file, so SMTP settings must come from the
# app's Secrets. Mirror them into the environment (once) so config.get_smtp_config,
# which reads os.getenv, finds them. Guarded: no secrets configured is fine.
try:
    for _key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                 "FROM_EMAIL", "GOOGLE_API_KEY"):
        if _key in st.secrets:
            os.environ.setdefault(_key, str(st.secrets[_key]))
except Exception:
    pass

st.set_page_config(page_title="Internbuddy")
st.title("Internbuddy — AI Internship Finder")
st.caption("Find internships matched to your profile, delivered as a report.")

with st.form("profile_form"):
    name = st.text_input("Name", placeholder="Your Name")
    stream = st.text_input("Educational stream", placeholder="e.g. B.Tech Computer Science")
    interest = st.text_input("Field of interest", placeholder="e.g. machine learning")
    email = st.text_input("Email", placeholder="name@mail.com")
    resume_link = st.text_input(
        "Google Drive resume link",
        placeholder="https://drive.google.com/file/d/.../view (shared: anyone with the link)",
    )
    gemini_api_key = st.text_input(
        "Your Gemini API key",
        type="password",
        help="Get a free key at https://aistudio.google.com/apikey — used only to rank your matches.",
    )
    report_format = st.radio("Report format", ["csv", "pdf", "both"], horizontal=True)
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

    for data, mime, filename in state.get("reports", []):
        st.download_button(
            f"⬇️ Download {filename}",
            data=data,
            file_name=filename,
            mime=mime,
            key=filename,
        )

    email_status = state.get("email_status", "")
    if email_status == "sent":
        st.success(f"Report emailed to {profile.email}.")
    else:
        st.info(f"Email status: {email_status}")
