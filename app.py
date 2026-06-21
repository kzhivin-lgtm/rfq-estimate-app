from __future__ import annotations
from pathlib import Path

import pandas as pd
import json
import re

import math
import time

from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from agents.detection_agent import run_detection_agent
from db.supabase_client import get_supabase_client
from db.repositories import (
    fetch_company_data,
    fetch_estimate_driver_quantities,
    fetch_rfq_detected_objects,
    fetch_rfq_run,
    upsert_rfq_detection_result,
)
from engine.routing import select_routes
from engine.estimate_engine import calculate_work_hours
from styles import apply_css
import os


st.set_page_config(
    page_title="RFQ Estimate App",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_css()


def get_company_id() -> str:
    return st.secrets.get("COMPANY_ID", "001")

def get_detection_agent_mode() -> str:
    return str(st.secrets.get("DETECTION_AGENT_MODE", "mock")).strip().lower()


def init_state():
    if "screen" not in st.session_state:
        st.session_state.screen = "upload"

    if "current_run_id" not in st.session_state:
        st.session_state.current_run_id = None

    if "uploaded_file_name" not in st.session_state:
        st.session_state.uploaded_file_name = None

    if "uploaded_file_bytes" not in st.session_state:
        st.session_state.uploaded_file_bytes = None


def go_to(screen: str):
    st.session_state.screen = screen
    st.rerun()


@st.cache_data(show_spinner=False)
def load_company_data_cached(company_id: str):
    client = get_supabase_client()
    return fetch_company_data(client, company_id)


# -----------------------------------------------------------------------------
# Product flow
# -----------------------------------------------------------------------------


# COMMON_POST_UPLOAD_LAYOUT_V1
def apply_post_upload_layout_css() -> None:
    st.markdown(
        """
<style>
:root {
    --post-upload-width: min(960px, calc(100vw - 56px));
    --post-upload-top: 88px;
}

html,
body,
.stApp,
div[data-testid="stAppViewContainer"],
section.main {
    background: #F1EFEF !important;
}

/* Canonical layout for all screens after Upload. */
.block-container {
    width: var(--post-upload-width) !important;
    max-width: none !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-top: var(--post-upload-top) !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    padding-bottom: 72px !important;
    background: #F1EFEF !important;
}

/* Upload screen remains its own centered exception. */
.stApp:has(.upload-screen-active) .block-container {
    width: 100% !important;
    max-width: none !important;
    padding: 0 !important;
}

.post-upload-title {
    font-family: var(--mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace) !important;
    color: #8049C6 !important;
    font-size: 40px !important;
    line-height: 1.1 !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em !important;
    margin: 0 0 var(--s5) 0 !important;
    padding: 0 !important;
}

.post-upload-subtitle {
    color: var(--ink-500, rgba(0, 0, 0, 0.52)) !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
    margin: calc(-1 * var(--s3, 16px)) 0 var(--s5, 32px) 0 !important;
    max-width: 760px !important;
}

.custom-progress-track {
    width: 100%;
    height: 12px;
    border-radius: 999px;
    background: #D85A5A;
    overflow: hidden;
}

.custom-progress-fill {
    height: 100%;
    min-width: 0;
    border-radius: 999px;
    background: #8049C6;
    transition: width 140ms linear;
}

.custom-progress-fill.is-running {
    background: linear-gradient(
        90deg,
        #8049C6 0%,
        #9A65DF 52%,
        #8049C6 100%
    );
}

/* White object-card substrate for File Review and later pages. */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1px solid rgba(42, 31, 44, 0.14) !important;
    border-radius: 16px !important;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.055) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border-radius: 16px !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_post_upload_header(title: str, subtitle: str | None = None) -> None:
    apply_post_upload_layout_css()

    st.markdown(
        f"<h1 class='post-upload-title'>{title}</h1>",
        unsafe_allow_html=True,
    )

    if subtitle:
        st.markdown(
            f"<div class='post-upload-subtitle'>{subtitle}</div>",
            unsafe_allow_html=True,
        )



def detect_uploaded_file_type(file_name: str) -> str:
    """Return a simple file type label for uploaded RFQ packages."""
    suffix = Path(file_name).suffix.lower().lstrip(".")

    if suffix == "pdf":
        return "pdf"
    if suffix in {"xlsx", "xls", "csv"}:
        return "spreadsheet"
    if suffix in {"png", "jpg", "jpeg"}:
        return "image"
    if suffix in {"dwg", "dxf"}:
        return "cad"

    return suffix or "unknown"


# First screen: minimal RFQ package upload.
def render_upload_screen(company_id=None):
    st.markdown(
        """
        <style>
        .stApp:has(.upload-screen-active) .block-container {
            height: 100vh !important;
            max-height: 100vh !important;
            padding: 0 !important;
            overflow: hidden !important;
        }

        .stApp:has(.upload-screen-active) .block-container > div {
            height: 100vh !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
            transform: translateY(-40px) !important;
        }

        html, body {
            height: 100% !important;
            overflow: hidden !important;
        }

        .stApp,
        div[data-testid="stAppViewContainer"],
        section.main {
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
        }

        .block-container {
            height: 100vh !important;
            max-height: 100vh !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            overflow: hidden !important;
        }

        .landing-title {
            text-align: center;
            font-size: 64px;
            line-height: 1.05;
            font-weight: 800;
            letter-spacing: -2px;
            margin: 150px 0 72px 0;
            color: var(--orange);
        }

        div[data-testid="stFileUploader"] {
            flex: 0 0 auto !important;
        }
        </style>

        <div class="upload-screen-active" style="display:none"></div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="landing-title">
            RFQ to Estimate to Proposal
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "📎 DROP OR UPLOAD",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()

        st.session_state.uploaded_file = uploaded_file
        st.session_state.uploaded_filename = uploaded_file.name
        st.session_state.uploaded_file_size = uploaded_file.size
        st.session_state.uploaded_file_type = detect_uploaded_file_type(uploaded_file.name)
        st.session_state.uploaded_file_bytes = file_bytes


        for key in [
            "processing_completed",
            "processing_error",
            "detection_result",
            "current_run_id",
        ]:
            st.session_state.pop(key, None)

        st.session_state.screen = "processing"
        st.rerun()









def render_processing_screen(company_id: str | None = None):
    # Same layout system as File Review / Objects / Object Detail.
    # No fixed overlay. No separate coordinate system.
    if st.session_state.get("processing_completed"):
        render_file_review_screen(company_id)
        return

    render_post_upload_header(
        "Reading your RFQ package",
        "AI Detection is analyzing the uploaded file and detecting estimate-scope objects.",
    )

    progress_slot = st.empty()

    def render_progress(progress_value: float) -> None:
        value = max(0.0, min(1.0, float(progress_value)))
        width = round(value * 100, 1)

        progress_slot.markdown(
            f"<div class='custom-progress-track'>"
            f"<div class='custom-progress-fill is-running' style='width:{width}%;'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    try:
        render_progress(0.04)

        file_name = st.session_state.get("uploaded_filename")
        file_bytes = st.session_state.get("uploaded_file_bytes")

        if not file_name:
            st.session_state.screen = "upload"
            st.rerun()

        if not file_bytes:
            uploaded_file = st.session_state.get("uploaded_file")
            if uploaded_file is not None:
                file_bytes = uploaded_file.getvalue()
                st.session_state.uploaded_file_bytes = file_bytes

        if not file_bytes:
            st.session_state.screen = "upload"
            st.rerun()

        active_company_id = company_id or st.secrets.get("COMPANY_ID", "001")

        # Fast local preparation zone.
        render_progress(0.12)

        # Soft-progress zone during the black-box Claude call.
        # Only the agent call runs in the background thread.
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                run_detection_agent,
                file_name=file_name,
                company_id=active_company_id,
                file_bytes=file_bytes,
            )

            while not future.done():
                elapsed = time.time() - start_time

                # Smoothly approaches 88%, but never reaches completion before Claude returns.
                soft_value = 0.12 + 0.76 * (1 - math.exp(-elapsed / 18))
                soft_value = min(soft_value, 0.88)

                render_progress(soft_value)
                time.sleep(0.15)

            detection_result = future.result()

        # Real post-processing zone.
        render_progress(0.90)

        if not isinstance(detection_result, dict):
            raise RuntimeError("Detection agent returned an invalid result.")

        rfq_run = detection_result.get("rfq_run") or {}
        run_id = rfq_run.get("run_id")

        if not run_id:
            raise RuntimeError("Detection result does not contain rfq_run.run_id.")

        st.session_state.detection_result = detection_result
        st.session_state.current_run_id = run_id

        render_progress(0.94)

        client = get_supabase_client()
        upsert_rfq_detection_result(client, detection_result)

        render_progress(1.0)

        st.session_state.processing_completed = True

        time.sleep(0.25)
        st.rerun()

    except Exception as exc:
        st.session_state.processing_error = str(exc)
        st.error(str(exc))

        if st.button("Back to upload"):
            st.session_state.screen = "upload"
            st.rerun()


def _is_empty_value(value) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip()
    return text == "" or text.lower() in {"none", "unknown", "nan", "null", "-"}


def split_text_to_points(value) -> list[str]:
    if _is_empty_value(value):
        return []

    text = str(value).strip()

    text = text.replace("•", "\n")
    text = text.replace("; ", "\n")
    text = text.replace(";", "\n")

    raw_parts = []
    for line in text.splitlines():
        line = line.strip(" \t-•")
        if not line:
            continue

        parts = re.split(r"(?<=[.!?])\s+(?=[A-ZА-Яא-ת0-9])", line)
        raw_parts.extend(parts)

    points = []
    for part in raw_parts:
        part = part.strip(" \t-•.;")
        if part and part.lower() not in {"none", "unknown"}:
            points.append(part)

    return points


def render_bullets(value, empty_text: str = "No major missing information detected.") -> None:
    points = split_text_to_points(value)

    if not points:
        st.caption(empty_text)
        return

    for point in points:
        st.markdown(f"- {point}")


def format_confidence(value) -> str:
    if _is_empty_value(value):
        return "—"

    try:
        return f"{float(value):.0f}%"
    except Exception:
        return str(value)


def format_quantity(row) -> str:
    quantity = row.get("quantity", 1)
    quantity_confidence = row.get("quantity_confidence", 0)

    try:
        q = float(quantity)
        q_text = str(int(q)) if q.is_integer() else str(round(q, 2))
    except Exception:
        q_text = str(quantity)

    try:
        qc = float(quantity_confidence)
    except Exception:
        qc = 0

    return f"{q_text}?" if qc < 70 else q_text


def _parse_dimensions(value) -> dict:
    if isinstance(value, dict):
        return value

    if _is_empty_value(value):
        return {}

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}

    return {}


def _dimension_part(label: str, value) -> str:
    try:
        number = float(value)
        if number <= 0:
            return f"{label} ?"
        if number.is_integer():
            return f"{label} {int(number)}"
        return f"{label} {round(number, 1)}"
    except Exception:
        return f"{label} ?"


def format_dimensions(value) -> str:
    dimensions = _parse_dimensions(value)

    width = dimensions.get("width", 0)
    depth = dimensions.get("depth", 0)
    height = dimensions.get("height", 0)
    unit = dimensions.get("unit", "mm")

    if _is_empty_value(unit):
        unit = "mm"

    return (
        f"{_dimension_part('W', width)} × "
        f"{_dimension_part('D', depth)} × "
        f"{_dimension_part('H', height)} {unit}"
    )


def render_file_review_screen(company_id: str):
    render_post_upload_header("File Review")

    client = get_supabase_client()
    run_id = st.session_state.get("current_run_id") or "RA-N01_run_001"

    run_df = fetch_rfq_run(client, run_id)
    objects_df = fetch_rfq_detected_objects(client, run_id)

    if run_df.empty:
        st.warning("No RFQ run found. Run detection first.")
        if st.button("Back to upload"):
            go_to("upload")
        return

    run = run_df.iloc[0].to_dict()

    col1, col2, col3 = st.columns(3)
    col1.metric("Project", run.get("project_name", "—"))
    col2.metric("Pages", run.get("pages_detected", 0))
    col3.metric("File quality", run.get("file_quality_label", "—"))

    st.divider()

    st.subheader("Missing information")
    render_bullets(
        run.get("missing_information", "none"),
        empty_text="No major missing information detected.",
    )

    with st.expander("Technical metadata", expanded=False):
        metadata_rows = [
            ("Project name", run.get("project_name", "—")),
            ("File name", run.get("file_name", "—")),
            ("Source type", run.get("source_type", "—")),
            ("Design partner", run.get("client_or_design_partner", "—")),
            ("Author", run.get("author", "—")),
            ("Document date", run.get("document_date", "—")),
            ("Language", run.get("language", "—")),
            ("File quality confidence", format_confidence(run.get("file_quality_confidence", 0))),
            ("Run ID", run.get("run_id", "—")),
            ("Status", run.get("status", "—")),
        ]

        st.dataframe(
            pd.DataFrame(metadata_rows, columns=["Field", "Value"]),
            width="stretch",
            hide_index=True,
        )

    st.divider()

    st.subheader("Detected objects")

    if objects_df.empty:
        st.warning("No objects detected.")
    else:
        for _, row in objects_df.iterrows():
            with st.container(border=True):
                top_left, top_mid, top_right = st.columns([5, 1, 1])

                top_left.subheader(row.get("object_name", "Unknown object"))
                top_mid.metric("Qty", format_quantity(row))
                top_right.metric("Confidence", format_confidence(row.get("confidence", 0)))

                dim_col, mat_col = st.columns([2, 3])

                with dim_col:
                    st.caption("Dimensions")
                    st.write(format_dimensions(row.get("dimensions_json", {})))

                with mat_col:
                    st.caption("Materials")
                    materials = row.get("detected_materials", "unknown")
                    st.write("—" if _is_empty_value(materials) else materials)

                notes = row.get("notes", "none")
                if not _is_empty_value(notes):
                    st.caption("Notes")
                    render_bullets(notes, empty_text="—")

    col_back, col_next = st.columns(2)

    if col_back.button("Back to upload"):
        go_to("upload")

    if col_next.button("Continue to objects", type="primary"):
        go_to("objects")

def render_objects_screen(company_id: str):
    st.title("Detected Objects")

    client = get_supabase_client()
    run_id = st.session_state.get("current_run_id") or "RA-N01_run_001"

    objects_df = fetch_rfq_detected_objects(client, run_id)

    if objects_df.empty:
        st.warning("No detected objects found.")
        if st.button("Back to File Review"):
            go_to("file_review")
        return

    for _, row in objects_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])

            col1.subheader(row.get("object_name", "Unknown object"))
            col1.caption(row.get("notes", ""))

            col2.metric("Qty", row.get("quantity", 1))
            col3.metric("Confidence", f"{row.get('confidence', 0)}%")

            st.write(f"**Materials:** {row.get('detected_materials', 'none')}")
            st.write(f"**Evidence pages:** {row.get('evidence_pages', 'none')}")
            st.write(f"**Dimensions:** {row.get('dimensions_json', {})}")

    col_back, col_next = st.columns(2)

    if col_back.button("Back to File Review"):
        go_to("file_review")

    if col_next.button("Continue to route preview", type="primary"):
        go_to("dev_dashboard")


# -----------------------------------------------------------------------------
# Dev dashboard
# -----------------------------------------------------------------------------

def render_connection_check():
    st.header("1. Supabase connection")

    try:
        client = get_supabase_client()
        st.success("Supabase client initialized.")
        return client
    except Exception as exc:
        st.error(str(exc))
        st.info("Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets.")
        st.stop()


def render_data_overview(company_id: str):
    st.header("2. Company data")

    data = load_company_data_cached(company_id)

    counts = pd.DataFrame(
        [
            {"table": name, "rows": len(df)}
            for name, df in data.items()
        ]
    )

    st.dataframe(counts, use_container_width=True, hide_index=True)

    with st.expander("Preview works"):
        st.dataframe(data["works"], use_container_width=True, height=420)

    with st.expander("Preview company machines"):
        st.dataframe(data["company_machines"], use_container_width=True, height=360)

    return data


def render_detection_agent_dev(company_id: str):
    st.header("3. Detection Agent")

    st.caption(
        "Mock Detection Agent v1: parses RFQ metadata, file quality and detected objects."
    )

    file_name = st.text_input(
        "RFQ file name",
        value="RA-N01_20260216.pdf",
        key="detection_file_name_dev",
    )

    dev_uploaded_file = st.file_uploader(
        "Optional PDF for real Anthropic detection",
        type=["pdf"],
        key="detection_file_dev_upload",
    )

    client = get_supabase_client()

    if st.button("Run Detection Agent", type="primary"):
        if dev_uploaded_file is not None:
            detection_result = run_detection_agent(
                file_name=dev_uploaded_file.name,
                company_id=company_id,
                file_bytes=dev_uploaded_file.getvalue(),
            )
        else:
            detection_result = run_detection_agent(
                file_name=file_name,
                company_id=company_id,
                file_bytes=None,
            )

        upsert_rfq_detection_result(client, detection_result)

        st.session_state["current_run_id"] = detection_result["rfq_run"]["run_id"]
        st.success(f"Detection result saved: {detection_result['rfq_run']['run_id']}")

    run_id = st.session_state.get("current_run_id", "RA-N01_run_001")

    run_df = fetch_rfq_run(client, run_id)
    objects_df = fetch_rfq_detected_objects(client, run_id)

    if run_df.empty:
        st.info("No RFQ run saved yet. Run the Detection Agent first.")
        return

    run = run_df.iloc[0].to_dict()

    col1, col2, col3 = st.columns(3)
    col1.metric("Project", run.get("project_name", "—"))
    col2.metric("File quality", run.get("file_quality_label", "—"))
    col3.metric("Confidence", f"{run.get('file_quality_confidence', 0)}%")

    with st.expander("RFQ run metadata", expanded=True):
        st.dataframe(run_df, use_container_width=True, hide_index=True)

    st.subheader("Detected objects")

    if objects_df.empty:
        st.warning("No detected objects found for this run.")
        return

    visible_cols = [
        "object_id",
        "object_name",
        "quantity",
        "quantity_explicit",
        "quantity_confidence",
        "confidence",
        "evidence_pages",
        "detected_materials",
        "dimensions_json",
        "notes",
    ]

    existing_cols = [col for col in visible_cols if col in objects_df.columns]

    st.dataframe(
        objects_df[existing_cols],
        use_container_width=True,
        hide_index=True,
        height=260,
    )


def render_route_preview(data: dict[str, pd.DataFrame]):
    st.header("4. Route selection preview")

    works = data.get("works", pd.DataFrame())
    company_machines = data.get("company_machines", pd.DataFrame())

    if works.empty:
        st.warning("No rows loaded from works. Check Supabase data import or RLS policies.")
        return pd.DataFrame()

    if company_machines.empty:
        st.warning("No rows loaded from company_machines. Check Supabase data import or RLS policies.")
        return pd.DataFrame()

    selected_routes = select_routes(works, company_machines)

    if selected_routes.empty:
        st.warning("No routes selected.")
        return selected_routes

    st.caption(
        "One selected route per work_family_code based on active company machines and route_priority."
    )

    columns_to_show = [
        "work_category",
        "work_family_code",
        "route_name",
        "execution_method",
        "machine_type",
        "service_code",
        "driver_code",
        "hours_per_unit",
    ]

    existing_columns = [
        col for col in columns_to_show
        if col in selected_routes.columns
    ]

    st.dataframe(
        selected_routes[existing_columns],
        use_container_width=True,
        height=420,
    )

    return selected_routes


def render_estimate_test(company_id: str, selected_routes: pd.DataFrame):
    st.header("5. Estimate driver quantities test")

    if selected_routes.empty:
        st.info("No selected routes available.")
        return

    estimate_id = st.text_input("estimate_id", value="RA-N01_run_001")
    object_id = st.text_input("object_id", value="01_kitchen")

    client = get_supabase_client()

    if st.button("Load driver quantities and calculate hours", type="primary"):
        quantities = fetch_estimate_driver_quantities(
            client=client,
            company_id=company_id,
            estimate_id=estimate_id,
            object_id=object_id,
        )

        if quantities.empty:
            st.warning("No rows found in estimate_driver_quantities for this estimate/object.")
            st.info("This is expected until the AI/takeoff layer writes driver quantities.")
            return

        st.subheader("Driver quantities")
        st.dataframe(quantities, use_container_width=True, hide_index=True)

        hours_df = calculate_work_hours(selected_routes, quantities)

        st.subheader("Calculated work hours")
        st.dataframe(hours_df, use_container_width=True, hide_index=True, height=480)

        st.metric("Total adjusted hours", round(hours_df["adjusted_hours"].sum(), 2))


def render_dev_dashboard(company_id: str):
    st.title("RFQ Estimate App")
    st.caption("Developer dashboard. Supabase-backed backend checks.")

    render_connection_check()

    if st.button("Refresh Supabase data"):
        load_company_data_cached.clear()
        st.rerun()

    data = render_data_overview(company_id)
    render_detection_agent_dev(company_id)
    selected_routes = render_route_preview(data)
    render_estimate_test(company_id, selected_routes)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    init_state()

    company_id = get_company_id()

    show_dev_nav = os.getenv("SHOW_DEV_NAV", "false").lower() in {"1", "true", "yes", "on"}

    if show_dev_nav:
        with st.sidebar:
            st.write("Navigation")
            st.caption(f"company_id: {company_id}")

            if st.button("Upload flow"):
                go_to("upload")

            if st.button("Dev dashboard"):
                go_to("dev_dashboard")

            if st.session_state.get("current_run_id"):
                st.caption(f"run_id: {st.session_state.current_run_id}")

    screen = st.session_state.screen

    if screen == "upload":
        render_upload_screen(company_id)
    elif screen == "processing":
        render_processing_screen(company_id)
    elif screen == "file_review":
        render_file_review_screen(company_id)
    elif screen == "objects":
        render_objects_screen(company_id)
    elif screen == "dev_dashboard":
        render_dev_dashboard(company_id)
    else:
        render_upload_screen(company_id)


if __name__ == "__main__":
    main()
