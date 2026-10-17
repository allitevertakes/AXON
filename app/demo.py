"""Small Streamlit demo for the AXON API.

Run with: streamlit run app/demo.py
"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

st.set_page_config(page_title="AXON demo", page_icon="🧭", layout="wide")
st.title("AXON | Career intelligence demo")
st.caption("Resume signals, job matches, skill gaps, and task-level automation signals.")
api_url = st.sidebar.text_input("AXON API", "http://127.0.0.1:8000").rstrip("/")


def api_call(path: str, *, payload: dict | None = None, file: bytes | None = None):
    if file is not None:
        boundary = "axon-demo-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="resume.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode() + file + f"\r\n--{boundary}--\r\n".encode()
        request = Request(api_url + path, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(api_url + path, data=body, headers={"Content-Type": "application/json"} if body else {})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = exc.read().decode(errors="replace") if isinstance(exc, HTTPError) else str(exc)
        st.error(f"API request failed: {detail}")
        return None


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
        st.dataframe(profile.get("skills", []), use_container_width=True, hide_index=True)
        st.caption(profile.get("notice", ""))

with right:
    st.subheader("2. Find jobs")
    keyword = st.text_input("Search Remotive", "Python")
    if st.button("Search jobs"):
        result = api_call("/market/jobs?keyword=" + keyword.strip().replace(" ", "%20"))
        if result:
            st.session_state["jobs_result"] = result
    jobs = st.session_state.get("jobs_result")
    if jobs:
        for job in jobs.get("jobs", []):
            st.markdown(f"**[{job['title']}]({job['url']})** · {job['company']}")
            st.caption(" · ".join(x for x in (job.get("category"), job.get("eligible_location"), job.get("salary")) if x))

st.divider()
st.subheader("3. Compare skills")
profile = st.session_state.get("resume_result") or {}
skill_names = [item.get("skill", "") for item in profile.get("skills", [])]
known_default = ", ".join(skill_names)
known_text = st.text_input("Candidate skills", known_default, help="Prefilled from the extracted resume skills; edit as needed.")
required_text = st.text_input("Required job skills", "Python, SQL")
optional_text = st.text_input("Optional job skills", "Docker")
if st.button("Analyze skill gap"):
    names = lambda value: [part.strip() for part in value.split(",") if part.strip()]
    result = api_call("/analysis/skill-gap", payload={"known_skills": names(known_text), "required_skills": names(required_text), "optional_skills": names(optional_text)})
    if result:
        st.json(result)

st.divider()
st.subheader("4. Assess task signals")
st.caption("Add true/false flags based on supplied job task information. This is a qualitative heuristic, not a job-loss prediction.")
task_json = st.text_area("Task input (JSON)", json.dumps({"title": "Example role", "tasks": [{"name": "Reconcile standard records", "routine": True, "digital": True, "rule_based": True}, {"name": "Resolve a customer concern", "human_judgment": True, "interpersonal": True, "contextual_decisions": True}]}, indent=2), height=220)
if st.button("Assess tasks"):
    try:
        payload = json.loads(task_json)
        result = api_call("/analysis/automation-risk", payload=payload)
        if result:
            st.json(result)
    except json.JSONDecodeError as exc:
        st.error(f"Check the JSON: {exc}")
