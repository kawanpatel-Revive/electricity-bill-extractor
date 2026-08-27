"""Canonical output schema derived from the reference workbook."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "number"
    calculated: bool = False


FIELDS = (
    Field("billing_month", "Billing Month", "text"),
    Field("meter_number", "Meter No.", "text"),
    Field("customer_id", "Customer ID", "text"),
    Field("tariff_category", "Tarrif Category", "text"),
    Field("contract_demand", "Contract Demand"),
    Field("actual_max_demand", "Actual Max demand"),
    Field("billing_demand", "Billing Demand"),
    Field("average_power_factor", "Avg PF %"),
    Field("kwh_consumed", "kWh (Units) Consumed"),
    Field("kwh_increase_percent", "% Increase in kWh", calculated=True),
    Field("night_units", "Night Hr. Units"),
    Field("night_units_percent", "% of Total units", "percent", calculated=True),
    Field("tou_kwh", "TOU kWh"),
    Field("tou_percent", "% of Total units", "percent", calculated=True),
    Field("one_third_total_units", "1/3 of Total Units", calculated=True),
    Field("night_concession_units", "E. Night Concession Units"),
    Field("solar_generation_units", "Solar Gen Units", calculated=True),
    Field("solar_net_billed_units", "Solar Net Billed Units", calculated=True),
    Field("solar_setoff_units", "Solar Setoff Units"),
    Field("solar_setoff_percent", "Solar Set-off units %", "percent", calculated=True),
    Field("solar_export_units", "Solar Surplus/Export Units"),
    Field("solar_export_percent", "Solar Surplus %", "percent", calculated=True),
    Field("solar_banking_units", "Solar Gen. Units considered for banking charges"),
    Field("solar_banking_percent", "Solar Banking Units %", "percent", calculated=True),
    Field("demand_charges", "Demand Charges"),
    Field("demand_charges_percent", "Demand Charges %", "percent", calculated=True),
    Field("excess_demand_charges", "Excess Demand Charges"),
    Field("energy_charges", "Energy Charges (Rs)"),
    Field("energy_charges_percent", "Energy Charges %", "percent", calculated=True),
    Field("fuel_surcharge", "Fuel Surcharge"),
    Field("fuel_surcharge_percent", "Fuel Surcharge %", "percent", calculated=True),
    Field("base_fppas", "Base FPPAS"),
    Field("fppas_charges", "FPPAS Charges"),
    Field("fppas_percent", "FPPAS %", "percent"),
    Field("power_factor_adjustment", "PF Adjust. (Rs)"),
    Field("night_rebate", "Night Rebate"),
    Field("ehv_rebate", "EHV Rebate"),
    Field("tou_charges", "TOU Charges"),
    Field("tou_charges_percent", "TOU Charges %", "percent", calculated=True),
    Field("total_energy_charges", "Total Energy/Consumption Charges", calculated=True),
    Field("total_consumption_charges", "Total Consumption Charges"),
    Field("electricity_duty", "Electricity Duty"),
    Field("current_month_bill", "Current bill Month", calculated=True),
    Field("solar_banking_charges", "Solar Banking (Rs1.1/kWh)"),
    Field("solar_credit", "Solar Credit (Rs.2.25/kWh) (Rs)"),
    Field("solar_setoff_credit", "Solar Set off Credit"),
    Field("wheeling_charges", "Wheeling charges"),
    Field("previous_dues", "Previous Dues"),
    Field("electricity_duty_credits", "Electricity Duty Credits"),
    Field("tou_charge_credits", "TOU Charge Credits"),
    Field("tds_credits", "TDS Credits"),
    Field("other_debits", "Other Debits"),
    Field("delayed_payment_charges", "Delayed Payment Charges"),
    Field("security_deposit_interest", "Security Deposit Interest"),
    Field("other_credits", "Other Credits"),
    Field("advance_adjustment", "Adv Payment/ Adjustment"),
    Field("calculated_adjustment", "Formula Adv Adjustment", calculated=True),
    Field("outstanding_arrears", "Outstanding Arrears"),
    Field("net_payable", "Net Payable"),
    Field("tcs", "TCS"),
    Field("total_payable", "Total Payable (Rs)"),
    Field("consumption_demand_unit_rate", "Total Consumption-Demand Charge Unit Rate\n\n", calculated=True),
    Field("consumption_unit_rate", "Unit Rate (Total Consumption Charge)", calculated=True),
    Field("net_less_demand_unit_rate", "Total Net Payable – Demand Charge Unit Rate", calculated=True),
    Field("total_payable_unit_rate", "Unit Rate (Total Payable)", calculated=True),
)

FIELD_BY_KEY = {field.key: field for field in FIELDS}
FIELD_KEYS = tuple(field.key for field in FIELDS)


def empty_record() -> dict[str, str | float | None]:
    return {field.key: None for field in FIELDS}
