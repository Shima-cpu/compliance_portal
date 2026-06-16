import json
import re
from pathlib import Path

import streamlit as st

APP_TITLE = "Compliance Process Guide"
DATA_FILE = Path("processes.json")


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🔎",
    layout="wide",
)


# ---------- Authentication ----------
def check_password() -> bool:
    """Simple password gate for internal MVP usage."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title(APP_TITLE)
    st.caption("Internal process knowledge base")

    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        expected_password = st.secrets.get("APP_PASSWORD", "")
        if not expected_password:
            st.error("APP_PASSWORD is not configured in Streamlit Secrets.")
            return False

        if password == expected_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False


if not check_password():
    st.stop()


# ---------- Data loading ----------
@st.cache_data
def load_processes() -> list[dict]:
    if not DATA_FILE.exists():
        st.error(f"Data file not found: {DATA_FILE}")
        return []

    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


processes = load_processes()


# ---------- Search helpers ----------
def normalize_text(value: str) -> str:
    value = value.lower().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def process_search_blob(process: dict) -> str:
    parts = [
        process.get("title", ""),
        process.get("category", ""),
        process.get("description", ""),
        process.get("when_to_use", ""),
        " ".join(process.get("keywords", [])),
    ]

    for step in process.get("steps", []):
        parts.append(step.get("title", ""))
        parts.append(step.get("text", ""))

    return normalize_text(" ".join(parts))


def score_process(process: dict, query: str) -> int:
    query = normalize_text(query)
    if not query:
        return 0

    query_terms = query.split()
    blob = process_search_blob(process)
    title = normalize_text(process.get("title", ""))
    keywords = [normalize_text(keyword) for keyword in process.get("keywords", [])]

    score = 0

    if query in title:
        score += 50

    if query in blob:
        score += 20

    for keyword in keywords:
        if query == keyword:
            score += 60
        elif query in keyword or keyword in query:
            score += 35

    for term in query_terms:
        if term in title:
            score += 10

        if term in blob:
            score += 5

        for keyword in keywords:
            if term in keyword:
                score += 8

    if all(term in blob for term in query_terms):
        score += 25
    else:
        score -= 20

    return score


def search_processes(all_processes: list[dict], query: str) -> list[dict]:
    results = []

    for process in all_processes:
        score = score_process(process, query)

        if score > 0:
            results.append({**process, "_score": score})

    return sorted(results, key=lambda item: item["_score"], reverse=True)


def render_process(process: dict) -> None:
    st.markdown("---")

    st.header(process["title"])
    st.caption(process.get("category", ""))
    st.write(process.get("description", ""))

    when_to_use = process.get("when_to_use")
    if when_to_use:
        st.subheader("When to use")
        st.write(when_to_use)

    warnings = process.get("warnings", [])
    if warnings:
        st.subheader("Warnings")
        for warning in warnings:
            st.warning(warning)

    steps = process.get("steps", [])
    if steps:
        st.subheader("Step-by-step guide")

        for index, step in enumerate(steps, start=1):
            with st.expander(
                f"Step {index}: {step.get('title', 'Untitled step')}",
                expanded=index == 1,
            ):
                st.write(step.get("text", ""))

                image_path = step.get("image")
                if image_path and Path(image_path).exists():
                    st.image(image_path, use_container_width=800)
                elif image_path:
                    st.caption(f"Image not found: {image_path}")

    related_templates = process.get("related_templates", [])
    if related_templates:
        st.subheader("Related templates")
        for template in related_templates:
            st.code(template, language="text")


# ---------- UI ----------
st.title(APP_TITLE)
st.caption("Search internal processes and follow step-by-step guides.")

top_left, top_right = st.columns([6, 1])

with top_right:
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.pop("selected_process_id", None)
        st.rerun()

st.markdown("---")

query = st.text_input(
    "Search process",
    placeholder="Example: SOF amount, forgery reset, sumsub reset...",
)

if not query:
    st.info("Start typing to search for a process.")
    st.stop()

results = search_processes(processes, query)

if not results:
    st.info("No matching processes found.")
    st.stop()

result_ids = [process["id"] for process in results]

if (
    "selected_process_id" not in st.session_state
    or st.session_state.selected_process_id not in result_ids
):
    st.session_state.selected_process_id = results[0]["id"]

with st.expander(f"Search results ({len(results)})", expanded=True):
    for process in results:
        if st.button(process["title"], key=f"result_{process['id']}"):
            st.session_state.selected_process_id = process["id"]
            st.rerun()

selected_process = next(
    process
    for process in results
    if process["id"] == st.session_state.selected_process_id
)

render_process(selected_process)
