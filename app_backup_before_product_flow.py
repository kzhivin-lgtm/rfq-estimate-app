from __future__ import annotations

import pandas as pd
import streamlit as st

from db.supabase_client import get_supabase_client
from db.repositories import (
    fetch_company_data,
    fetch_estimate_driver_quantities,
    upsert_rfq_detection_result,
    fetch_rfq_run,
    fetch_rfq_detected_objects,
)
from engine.routing import select_routes
from engine.estimate_engine import calculate_work_hours
from styles import apply_css

from agents.detection_agent import run_detection_agent

st.set_page_config(
    page_title="RFQ Estimate App",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_css()


def get_company_id() -> str:
    return st.secrets.get("COMPANY_ID", "001")


def render_header():
    st.title("RFQ Estimate App")
    st.caption("Supabase-backed estimating workspace. Stable demo is separate.")


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


@st.cache_data(show_spinner=False)
def load_company_data_cached(company_id: str):
    client = get_supabase_client()
    return fetch_company_data(client, company_id)


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

def render_detection_agent(company_id: str):
    st.header("3. Detection Agent")

    st.caption(
        "Mock Detection Agent v1: parses RFQ metadata, file quality and detected objects."
    )

    file_name = st.text_input(
        "RFQ file name",
        value="RA-N01_20260216.pdf",
        key="detection_file_name",
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
    st.header("3. Route selection preview")

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
    st.header("4. Estimate driver quantities test")

    estimate_id = st.text_input("estimate_id", value="RA-N01")
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


def main():
    render_header()

    company_id = get_company_id()
    st.caption(f"company_id: {company_id}")

    render_connection_check()

    if st.button("Refresh Supabase data"):
        load_company_data_cached.clear()
        st.rerun()

    data = render_data_overview(company_id)
    render_detection_agent(company_id)
    selected_routes = render_route_preview(data)
    render_estimate_test(company_id, selected_routes)


if __name__ == "__main__":
    main()
