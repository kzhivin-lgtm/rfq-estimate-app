from __future__ import annotations

import pandas as pd


def _as_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def build_driver_quantity_map(driver_quantities: pd.DataFrame) -> dict[str, float]:
    if driver_quantities.empty:
        return {}

    result: dict[str, float] = {}

    for _, row in driver_quantities.iterrows():
        code = str(row.get("driver_code", "none"))
        result[code] = result.get(code, 0.0) + _as_float(row.get("quantity", 0))

    return result


def calculate_work_hours(
    selected_routes: pd.DataFrame,
    driver_quantities: pd.DataFrame,
) -> pd.DataFrame:
    qty_map = build_driver_quantity_map(driver_quantities)
    rows = []

    for _, route in selected_routes.iterrows():
        driver_code = str(route.get("driver_code", "none"))
        secondary_driver_code = str(route.get("secondary_driver_code", "none"))

        primary_qty = qty_map.get(driver_code, 0.0) if driver_code != "none" else 0.0
        secondary_qty = qty_map.get(secondary_driver_code, 0.0) if secondary_driver_code != "none" else 0.0

        setup = _as_float(route.get("setup_hours", 0))
        hpu = _as_float(route.get("hours_per_unit", 0))
        secondary_hpu = _as_float(route.get("secondary_hours_per_unit", 0))
        complexity = _as_float(route.get("complexity_factor_default", 1), 1)

        method = str(route.get("execution_method", "manual"))

        if method == "subcontract":
            base_hours = 0.0
        else:
            base_hours = setup + primary_qty * hpu + secondary_qty * secondary_hpu

        adjusted_hours = base_hours * complexity

        rows.append({
            "work_category": route.get("work_category", "none"),
            "work_family_name": route.get("work_family_name", "none"),
            "route_name": route.get("route_name", "none"),
            "execution_method": method,
            "labor_code": route.get("labor_code", "none"),
            "machine_type": route.get("machine_type", "none"),
            "driver_code": driver_code,
            "driver_quantity": primary_qty,
            "secondary_driver_code": secondary_driver_code,
            "secondary_driver_quantity": secondary_qty,
            "setup_hours": setup,
            "base_hours": round(base_hours, 4),
            "adjusted_hours": round(adjusted_hours, 4),
        })

    return pd.DataFrame(rows)
