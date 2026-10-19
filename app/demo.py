
"""Small Streamlit demo for the AXON API.

Run with: python -m streamlit run app/demo.py
"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

st.set_page_config(page_title="AXON demo", page_icon="🧭", layout="wide")
st.title("AXON | Career intelligence demo")
st.caption(
    "Resume signals, job matches, skill gaps, learning recommendations, "
    "and task-level automation signals."
)
api_url = st.sidebar.text_input(
    "AXON API", "http://127.0.0.1:8000"
).rstrip("/")


def api_call(
    path: str,
    *,
    payload: dict | None = None,
    file: bytes | None = None,
):
    if file is not None:
        boundary = "axon-demo-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="resume.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode() + file + f"\r\n--{boundary}--\r\n".encode()
        request = Request(
            api_url + path,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            },
        )
    else:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            api_url + path,
            data=body,
            headers=(
                {"Content-Type": "application/json"} if body else {}
            ),
        )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = (
            exc.read().decode(errors="replace")
            if isinstance(exc, HTTPError)
            else str(exc)
        )
        st.error(f"API request failed: {detail}")
        return None


def parse_names(value: str) -> list[str]:
    """Parse comma-separated skill names."""
    return [part.strip() for part in value.split(",") if part.strip()]


left, right = st.columns(2)

with left:
    st.subheader("1. Resume profile")
    resume = st.file_uploader("Upload a text-based PDF", type=["pdf"])
    if resume and st.button("Extract profile", type="primary"):
        result = api_call("/profile/resume", file=resume.getvalue())
        if result:
            st.session_state["resume_result"] = result

    profile = st.session_state.get("resume_result")
    if profile:
        st.metric("Skills detected", profile.get("skills_detected", 0))
        st.dataframe(
            profile.get("skills", []),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(profile.get("notice", ""))
        with st.expander("Education and projects"):
            st.write("Education")
            st.json(profile.get("education", []))
            st.write("Projects")
            st.json(profile.get("projects", []))

with right:
    st.subheader("2. Find jobs")
    keyword = st.text_input("Search Remotive", "Python")
    if st.button("Search jobs"):
        result = api_call(
            "/market/jobs?keyword=" + keyword.strip().replace(" ", "%20")
        )
        if result:
            st.session_state["jobs_result"] = result

    jobs = st.session_state.get("jobs_result")
    if jobs:
        for job in jobs.get("jobs", []):
            st.markdown(
                f"**[{job['title']}]({job['url']})** · {job['company']}"
            )
            st.caption(
                " · ".join(
                    item
                    for item in (
                        job.get("category"),
                        job.get("eligible_location"),
                        job.get("salary"),
                    )
                    if item
                )
            )

st.divider()

st.divider()
st.subheader("Saved profiles | Passport")

if st.button("Load saved profiles"):
    result = api_call("/profile/saved?limit=20")
    if result is not None:
        profiles = (
            result.get("profiles", [])
            if isinstance(result, dict)
            else result
        )
        st.session_state["saved_profiles"] = profiles

saved_profiles = st.session_state.get("saved_profiles", [])

if not saved_profiles:
    st.caption("Load saved profiles to browse previously uploaded resumes.")
else:
    profile_options = {
        f"#{item['id']} | {item['filename']} | {item['created_at']}": item["id"]
        for item in saved_profiles
    }

    selected_label = st.selectbox(
        "Choose a saved profile",
        list(profile_options.keys()),
    )

    if st.button("Open saved profile"):
        selected_id = profile_options[selected_label]
        result = api_call(f"/profile/saved/{selected_id}")
        if result is not None:
            st.session_state["saved_profile_detail"] = result

    saved_detail = st.session_state.get("saved_profile_detail")

    if saved_detail:
        st.markdown(f"**Resume:** {saved_detail['filename']}")
        st.caption(f"Saved on: {saved_detail['created_at']}")

        st.markdown("**Extracted skills**")
        st.dataframe(
            saved_detail.get("skills", []),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Education and projects"):
            st.write("Education")
            st.json(saved_detail.get("education", []))
            st.write("Projects")
            st.json(saved_detail.get("projects", []))


st.subheader("3. Compare skills and build a learning path")

profile = st.session_state.get("resume_result") or {}
skill_names = [
    item.get("skill", "")
    for item in profile.get("skills", [])
    if item.get("skill")
]
known_default = ", ".join(skill_names)

known_text = st.text_input(
    "Candidate skills",
    known_default,
    help="Prefilled from your extracted resume skills. Edit as needed.",
    key="candidate_skills",
)
required_text = st.text_input(
    "Required job skills", "Python, SQL", key="required_skills"
)
optional_text = st.text_input(
    "Optional job skills", "Docker", key="optional_skills"
)

skill_payload = {
    "known_skills": parse_names(known_text),
    "required_skills": parse_names(required_text),
    "optional_skills": parse_names(optional_text),
}

col_gap, col_path = st.columns(2)

with col_gap:
    if st.button("Analyze skill gap"):
        result = api_call("/analysis/skill-gap", payload=skill_payload)
        if result:
            st.session_state["skill_gap_result"] = result

with col_path:
    if st.button("Generate learning path", type="primary"):
        result = api_call(
            "/analysis/learning-path",
            payload=skill_payload,
        )
        if result:
            st.session_state["learning_path_result"] = result

gap_result = st.session_state.get("skill_gap_result")
if gap_result:
    st.markdown("#### Skill-gap analysis")
    coverage = gap_result.get("coverage_score")
    if coverage is not None:
        st.metric("Required-skill coverage", f"{coverage:.1%}")
    st.write("**Matched skills**")
    st.write(", ".join(gap_result.get("matched_skills", [])) or "None identified")
    st.write("**Missing required skills**")
    st.write(", ".join(gap_result.get("missing_skills", [])) or "None identified")
    st.write("**Missing optional skills**")
    st.write(
        ", ".join(gap_result.get("optional_missing_skills", []))
        or "None identified"
    )

path_result = st.session_state.get("learning_path_result")
if path_result:
    st.markdown("#### Your learning recommendations")
    coverage = path_result.get("coverage_score")
    if coverage is not None:
        st.metric("Required-skill coverage", f"{coverage:.1%}")

    recommendations = path_result.get("recommendations", [])
    if not recommendations:
        st.success(
            "No skill gaps were identified from the skills and requirements supplied."
        )
    else:
        for item in recommendations:
            priority = item.get("priority", "unspecified").upper()
            st.markdown(
                f"**{item.get('skill', 'Unknown skill')}** · {priority} priority"
            )
            st.write(item.get("reason", ""))
            st.write(f"Suggested action: {item.get('suggested_action', '')}")
            st.divider()

    st.caption(
        "Recommendations are generated from the skill names supplied. "
        "They are starting points, not verified assessments of proficiency."
    )

st.divider()
st.subheader("4. Assess task signals")
st.caption(
    "Add true/false flags based on supplied job task information. "
    "This is a qualitative heuristic, not a job-loss prediction."
)

default_tasks = {
    "title": "Example role",
    "tasks": [
        {
            "name": "Reconcile standard records",
            "routine": True,
            "digital": True,
            "rule_based": True,
        },
        {
            "name": "Resolve a customer concern",
            "human_judgment": True,
            "interpersonal": True,
            "contextual_decisions": True,
        },
    ],
}
task_json = st.text_area(
    "Task input (JSON)",
    json.dumps(default_tasks, indent=2),
    height=220,
)

if st.button("Assess tasks"):
    try:
        payload = json.loads(task_json)
        result = api_call("/analysis/automation-risk", payload=payload)
        if result:
            st.session_state["automation_risk_result"] = result
    except json.JSONDecodeError as exc:
        st.error(f"Check the JSON: {exc}")

risk_result = st.session_state.get("automation_risk_result")
if risk_result:
    st.json(risk_result)
