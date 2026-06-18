from __future__ import annotations

import pandas as pd
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


st.set_page_config(
    page_title="RFQ Estimate App",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_css()


def get_company_id() -> str:
    return st.secrets.get("COMPANY_ID", "001")


def init_state():
    if "screen" not in st.session_state:
        st.session_state.screen = "upload"

    if "current_run_id" not in st.session_state:
        st.session_state.current_run_id = None

    if "uploaded_file_name" not in st.session_state:
        st.session_state.uploaded_file_name = None


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

def render_upload_screen(company_id: str):
    st.title("Drop or Upload")
    st.caption("Upload an RFQ package to start object detection and file quality review.")

    uploaded_file = st.file_uploader(
        "Upload RFQ file",
        type=["pdf", "png", "jpg", "jpeg", "dwg", "dxf", "xlsx", "csv"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        st.session_state.uploaded_file_name = uploaded_file.name
        st.success(f"File selected: {uploaded_file.name}")

    file_name = st.session_state.get("uploaded_file_name") or "RA-N01_20260216.pdf"

    st.text_input(
        "RFQ file name",
        value=file_name,
        key="manual_file_name",
    )

    if st.button("Prepare object detection", type="primary"):
        st.session_state.uploaded_file_name = st.session_state.manual_file_name
        go_to("processing")


def render_processing_screen(company_id: str):
    st.title("Preparing object estimates")
    st.caption("Running Detection Agent v1.")

    file_name = st.session_state.get("uploaded_file_name") or "RA-N01_20260216.pdf"

    with st.spinner("Detecting RFQ metadata, file quality and objects..."):
        client = get_supabase_client()

        detection_result = run_detection_agent(
            file_name=file_name,
            company_id=company_id,
        )

        upsert_rfq_detection_result(client, detection_result)

        run_id = detection_result["rfq_run"]["run_id"]
        st.session_state.current_run_id = run_id

    st.success(f"Detection completed: {st.session_state.current_run_id}")

    if st.button("Review detected file", type="primary"):
        go_to("file_review")


def render_file_review_screen(company_id: str):
    st.title("File Review")

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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Project", run.get("project_name", "—"))
    col2.metric("Pages", run.get("pages_detected", 0))
    col3.metric("File quality", run.get("file_quality_label", "—"))
    col4.metric("Confidence", f"{run.get('file_quality_confidence', 0)}%")

    st.subheader("Detected metadata")

    metadata_rows = [
        ("Project name", run.get("project_name", "—")),
        ("File name", run.get("file_name", "—")),
        ("Source type", run.get("source_type", "—")),
        ("Design partner", run.get("client_or_design_partner", "—")),
        ("Author", run.get("author", "—")),
        ("Document date", run.get("document_date", "—")),
        ("Language", run.get("language", "—")),
        ("Missing information", run.get("missing_information", "—")),
    ]

    st.dataframe(
        pd.DataFrame(metadata_rows, columns=["Field", "Value"]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Detected objects")

    if objects_df.empty:
        st.warning("No objects detected.")
    else:
        visible_cols = [
            "object_id",
            "object_name",
            "quantity",
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
            height=300,
        )

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

    client = get_supabase_client()

    if st.button("Run Detection Agent", type="primary"):
        detection_result = run_detection_agent(
            file_name=file_name,
            company_id=company_id,
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
