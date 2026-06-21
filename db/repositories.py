from __future__ import annotations

import pandas as pd
from supabase import Client


def fetch_table(
    client: Client,
    table_name: str,
    order_by: str | None = None,
    filters: dict | None = None,
) -> pd.DataFrame:
    query = client.table(table_name).select("*")

    if filters:
        for key, value in filters.items():
            query = query.eq(key, value)

    if order_by:
        query = query.order(order_by)

    response = query.execute()
    return pd.DataFrame(response.data or [])


def fetch_company_data(client: Client, company_id: str) -> dict[str, pd.DataFrame]:
    return {
        "labor": fetch_table(client, "labor", filters={"company_id": company_id}),
        "materials": fetch_table(client, "materials", filters={"company_id": company_id}),
        "works": fetch_table(client, "works", order_by="sort_order", filters={"company_id": company_id}),
        "company_machines": fetch_table(client, "company_machines", order_by="industry", filters={"company_id": company_id}),
        "overhead_settings": fetch_table(client, "overhead_settings", filters={"company_id": company_id}),
        "overhead_monthly": fetch_table(client, "overhead_monthly", filters={"company_id": company_id}),
        "work_drivers": fetch_table(client, "work_drivers", order_by="sort_order"),
        "machining_point_rules": fetch_table(client, "machining_point_rules", order_by="sort_order"),
    }


def fetch_estimate_driver_quantities(
    client: Client,
    company_id: str,
    estimate_id: str,
    object_id: str | None = None,
) -> pd.DataFrame:
    filters = {"company_id": company_id, "estimate_id": estimate_id}
    if object_id:
        filters["object_id"] = object_id

    return fetch_table(
        client,
        "estimate_driver_quantities",
        order_by="driver_code",
        filters=filters,
    )


def upsert_rfq_detection_result(client: Client, detection_result: dict) -> None:
    rfq_run = detection_result["rfq_run"]
    detected_objects = detection_result["detected_objects"]

    run_id = rfq_run["run_id"]

    client.table("rfq_runs").upsert(
        rfq_run,
        on_conflict="run_id",
    ).execute()

    client.table("rfq_detected_objects").delete().eq(
        "run_id",
        run_id,
    ).execute()

    if detected_objects:
        client.table("rfq_detected_objects").upsert(
            detected_objects,
            on_conflict="run_id,object_id",
        ).execute()


def fetch_rfq_run(client: Client, run_id: str) -> pd.DataFrame:
    return fetch_table(
        client,
        "rfq_runs",
        filters={"run_id": run_id},
    )


def fetch_rfq_detected_objects(client: Client, run_id: str) -> pd.DataFrame:
    return fetch_table(
        client,
        "rfq_detected_objects",
        order_by="object_id",
        filters={"run_id": run_id},
    )
