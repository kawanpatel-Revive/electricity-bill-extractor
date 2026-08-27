"""Deterministic calculations for fields not printed directly on a bill."""

from datetime import datetime

from bill_extractor.models import BillRecord
from bill_extractor.utils import safe_divide, sum_known


def calculate_record(values: dict[str, str | float | None]) -> None:
    """Fill derived fields without overwriting provider-extracted values."""
    def number(key: str) -> float | None:
        value = values.get(key)
        return float(value) if isinstance(value, (int, float)) else None

    def fill(key: str, value: float | None) -> None:
        if values.get(key) is None and value is not None:
            values[key] = value

    kwh = number("kwh_consumed")
    night = number("night_units")
    tou = number("tou_kwh")
    setoff = number("solar_setoff_units")
    export = number("solar_export_units")
    banking = number("solar_banking_units")
    generation = number("solar_generation_units")
    total_consumption = number("total_consumption_charges")
    demand = number("demand_charges")
    total_payable = number("total_payable")

    fill("night_units_percent", safe_divide(night, kwh))
    fill("tou_percent", safe_divide(tou, kwh))
    fill("one_third_total_units", kwh / 3 if kwh is not None else None)
    fill("solar_generation_units", sum_known(export, banking))
    generation = number("solar_generation_units")
    fill("solar_net_billed_units", kwh - setoff if kwh is not None and setoff is not None else None)
    fill("solar_setoff_percent", safe_divide(setoff, generation))
    fill("solar_export_percent", safe_divide(export, generation))
    fill("solar_banking_percent", safe_divide(banking, generation))
    fill("demand_charges_percent", safe_divide(demand, total_consumption))
    fill("energy_charges_percent", safe_divide(number("energy_charges"), total_consumption))
    fill("fuel_surcharge_percent", safe_divide(number("fuel_surcharge"), total_consumption))
    fill("tou_charges_percent", safe_divide(number("tou_charges"), total_consumption))
    fill("total_energy_charges", total_consumption)
    fill("current_month_bill", sum_known(total_consumption, number("electricity_duty")))

    adjustment_parts = [
        number("solar_banking_charges"),
        number("tcs"),
        number("solar_credit"),
        number("solar_setoff_credit"),
        number("electricity_duty_credits"),
        number("tou_charge_credits"),
        number("tds_credits"),
        number("other_debits"),
        number("other_credits"),
        number("security_deposit_interest"),
    ]
    if any(part is not None for part in adjustment_parts):
        fill("calculated_adjustment", sum(part or 0 for part in adjustment_parts))

    fill("consumption_unit_rate", safe_divide(total_consumption, kwh))
    fill(
        "consumption_demand_unit_rate",
        safe_divide(
            total_consumption - demand
            if total_consumption is not None and demand is not None
            else None,
            kwh,
        ),
    )
    fill(
        "net_less_demand_unit_rate",
        safe_divide(
            total_payable - demand if total_payable is not None and demand is not None else None,
            number("solar_net_billed_units"),
        ),
    )
    fill("total_payable_unit_rate", safe_divide(total_payable, kwh))


def calculate_kwh_change(records: list[BillRecord]) -> None:
    """Calculate month-over-month kWh change for each customer after sorting."""
    previous: dict[str, float] = {}
    for record in records:
        customer = str(record.values.get("customer_id") or record.filename)
        current = record.values.get("kwh_consumed")
        if isinstance(current, (int, float)):
            prior = previous.get(customer)
            if prior not in (None, 0):
                record.values["kwh_increase_percent"] = (float(current) - prior) / prior
            previous[customer] = float(current)


def month_sort_key(record: BillRecord) -> tuple[str, datetime, str]:
    month = record.values.get("billing_month")
    try:
        parsed = datetime.strptime(str(month), "%b-%Y")
    except (TypeError, ValueError):
        parsed = datetime.max
    return str(record.values.get("customer_id") or ""), parsed, record.filename
