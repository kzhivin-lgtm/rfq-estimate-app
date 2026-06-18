from __future__ import annotations

import pandas as pd


def _active_machine_types(company_machines: pd.DataFrame) -> set[str]:
    if company_machines.empty:
        return set()

    active_col = company_machines["active"].astype(str).str.lower().isin(["true", "1", "yes"])
    return set(company_machines.loc[active_col, "machine_type"].astype(str))


def is_route_available(route: pd.Series, active_machines: set[str]) -> bool:
    method = str(route.get("execution_method", "manual"))
    machine_type = str(route.get("machine_type", "none"))
    service_code = str(route.get("service_code", "none"))

    if method == "machine":
        return machine_type != "none" and machine_type in active_machines

    if method == "subcontract":
        return service_code != "none"

    if method in {"manual", "overhead"}:
        return True

    return False


def select_routes(works: pd.DataFrame, company_machines: pd.DataFrame) -> pd.DataFrame:
    if works.empty:
        return works.copy()

    active_machines = _active_machine_types(company_machines)
    active_works = works[works["active"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()

    selected_rows = []

    for family_code, group in active_works.groupby("work_family_code", sort=False):
        group = group.sort_values(["route_priority", "sort_order"], ascending=[True, True])

        available = [
            row for _, row in group.iterrows()
            if is_route_available(row, active_machines)
        ]

        if available:
            selected_rows.append(available[0])
        else:
            selected_rows.append(group.iloc[0])

    return pd.DataFrame(selected_rows).reset_index(drop=True)
