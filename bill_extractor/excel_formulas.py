"""Excel formulas mapped by field key from Sample_Spreadsheet.xlsx.

Keep the sample's calculation relationships independent of column positions.
Literal arithmetic in source adjustment cells cannot be reconstructed from
aggregated bill values and remains an editable numeric input.
"""

from openpyxl.utils import get_column_letter

from bill_extractor.schema import FIELDS


COLUMNS = {field.key: get_column_letter(i) for i, field in enumerate(FIELDS, 1)}


def row_formulas(row: int, previous_row: int | None = None) -> dict[str, str]:
    def ref(key):
        return f"{COLUMNS[key]}{row}"

    def ratio(numerator, denominator):
        a, b = ref(numerator), ref(denominator)
        return f'=IF(AND(ISNUMBER({a}),ISNUMBER({b}),{b}<>0),{a}/{b},"-")'

    def total(keys, required=()):
        cells = ",".join(ref(key) for key in keys)
        condition = (
            "AND(" + ",".join(f"ISNUMBER({ref(key)})" for key in required) + ")"
            if required else f"COUNT({cells})>0"
        )
        return f'=IF({condition},SUM({cells}),"-")'

    formulas = {}
    for target, numerator, denominator in (
        ("night_units_percent", "night_units", "kwh_consumed"),
        ("tou_percent", "tou_kwh", "kwh_consumed"),
        ("solar_setoff_percent", "solar_setoff_units", "solar_generation_units"),
        ("solar_export_percent", "solar_export_units", "solar_generation_units"),
        ("solar_banking_percent", "solar_banking_units", "solar_generation_units"),
        ("demand_charges_percent", "demand_charges", "total_energy_charges"),
        ("energy_charges_percent", "energy_charges", "total_energy_charges"),
        ("fuel_surcharge_percent", "fuel_surcharge", "total_energy_charges"),
        ("tou_charges_percent", "tou_charges", "total_energy_charges"),
        ("consumption_unit_rate", "total_energy_charges", "kwh_consumed"),
        ("total_payable_unit_rate", "total_payable", "kwh_consumed"),
    ):
        formulas[target] = ratio(numerator, denominator)
    formulas["solar_generation_units"] = total(("solar_export_units", "solar_banking_units"))
    kwh, setoff = ref("kwh_consumed"), ref("solar_setoff_units")
    formulas["solar_net_billed_units"] = f'=IF(AND(ISNUMBER({kwh}),ISNUMBER({setoff})),{kwh}-{setoff},"-")'
    formulas["total_energy_charges"] = total((
        "demand_charges", "excess_demand_charges", "energy_charges", "fuel_surcharge",
        "base_fppas", "fppas_charges", "power_factor_adjustment", "night_rebate",
        "ehv_rebate", "tou_charges",
    ), ("demand_charges", "energy_charges"))
    formulas["current_month_bill"] = total(("total_consumption_charges", "electricity_duty"), ("total_consumption_charges",))
    formulas["calculated_adjustment"] = total((
        "solar_banking_charges", "solar_credit", "solar_setoff_credit", "wheeling_charges",
        "previous_dues", "electricity_duty_credits", "tou_charge_credits", "tds_credits",
        "security_deposit_interest", "other_credits", "other_debits",
    ))
    formulas["net_payable"] = total(("current_month_bill", "calculated_adjustment", "delayed_payment_charges", "outstanding_arrears"), ("current_month_bill",))
    formulas["total_payable"] = total(("net_payable", "tcs"), ("net_payable",))
    for target, amount in (("consumption_demand_unit_rate", "total_energy_charges"), ("net_less_demand_unit_rate", "total_payable")):
        a, demand = ref(amount), ref("demand_charges")
        formulas[target] = f'=IF(AND(ISNUMBER({a}),ISNUMBER({demand}),ISNUMBER({kwh}),{kwh}<>0),({a}-{demand})/{kwh},"-")'
    if previous_row is not None:
        previous = f"{COLUMNS['kwh_consumed']}{previous_row}"
        formulas["kwh_increase_percent"] = f'=IF(AND(ISNUMBER({kwh}),ISNUMBER({previous}),{previous}<>0),({kwh}-{previous})/{previous},"-")'
    return formulas


# The sample has a mixed SUM/AVERAGE summary and a second units/payable total row.
SUMMARY_AVERAGES = frozenset((
    "average_power_factor", "kwh_consumed", "night_units", "night_units_percent",
    "tou_kwh", "tou_percent", "one_third_total_units", "solar_setoff_percent",
    "solar_export_percent", "solar_banking_units", "solar_banking_percent",
    "demand_charges_percent", "energy_charges_percent", "fuel_surcharge_percent",
    "tou_charges_percent", "current_month_bill", "net_payable", "total_payable",
    "consumption_demand_unit_rate", "consumption_unit_rate", "net_less_demand_unit_rate",
    "total_payable_unit_rate",
))
SUMMARY_SUMS = frozenset((
    "solar_generation_units", "demand_charges", "energy_charges", "fuel_surcharge",
    "power_factor_adjustment", "ehv_rebate", "tou_charges", "total_energy_charges",
    "total_consumption_charges", "electricity_duty", "solar_banking_charges",
    "advance_adjustment", "calculated_adjustment", "outstanding_arrears",
))
TOTAL_SUMS = frozenset(("kwh_consumed", "night_units", "tou_kwh", "one_third_total_units", "net_payable", "total_payable"))
