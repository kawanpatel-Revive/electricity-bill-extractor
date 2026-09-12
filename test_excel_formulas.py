from copy import deepcopy
from io import BytesIO

from openpyxl import load_workbook
import pytest

from bill_extractor.export import export_excel
from bill_extractor.models import BillRecord
from bill_extractor.formula_cache import save_with_formula_results


def test_formula_export_preserves_inputs_and_groups_customers():
    records = [BillRecord({"customer_id": customer, "kwh_consumed": units,
                           "meter_number": "=untrusted", "total_payable": 123},
                          "UGVCL", "bill.pdf", [1])
               for customer, units in [("a", 100), ("b", 0), ("a", 200)]]
    original = deepcopy(records)
    workbook = load_workbook(BytesIO(export_excel(records)))
    sheet = workbook["Extracted Bills"]
    assert records == original
    assert sheet["B2"].data_type == "s"
    assert sheet["J2"].value == "-"
    assert sheet["J3"].value == "-"
    assert sheet["J4"].value == '=IF(AND(ISNUMBER(I4),ISNUMBER(I2),I2<>0),(I4-I2)/I2,"-")'
    assert sheet["J4"].number_format == "0.00%"
    # Sample references must follow the reordered adjustment/payable columns.
    assert sheet["BE2"].value == '=IF(COUNT(AR2,AS2,AT2,AU2,AV2,AW2,AX2,AY2,BB2,BC2,AZ2)>0,SUM(AR2,AS2,AT2,AU2,AV2,AW2,AX2,AY2,BB2,BC2,AZ2),"-")'
    assert sheet["BI2"].value == '=IF(AND(ISNUMBER(BG2)),SUM(BG2,BH2),"-")'
    assert sheet["BK2"].value == '=IF(AND(ISNUMBER(AN2),ISNUMBER(I2),I2<>0),AN2/I2,"-")'
    summary = workbook["Summary"]
    assert summary["I2"].value == '=IF(COUNT(\'Extracted Bills\'!I2,\'Extracted Bills\'!I4)>0,AVERAGE(\'Extracted Bills\'!I2,\'Extracted Bills\'!I4),"-")'
    assert "SUM(" in summary["I3"].value
    assert "I3" in summary["I4"].value
    assert workbook.calculation.calcMode == "auto"
    assert workbook.calculation.fullCalcOnLoad
    assert sheet.auto_filter.ref == "A1:BM4"


def test_empty_export_keeps_headers():
    workbook = load_workbook(BytesIO(export_excel([])))
    assert workbook["Extracted Bills"].max_row == 1
    assert "Summary" not in workbook.sheetnames


def test_cached_results_include_dependencies_summaries_and_missing_values():
    record = BillRecord({
        "customer_id": "a", "kwh_consumed": 100, "night_units": 25,
        "demand_charges": 100, "energy_charges": 900, "fuel_surcharge": 100,
        "total_consumption_charges": 1100, "electricity_duty": 100,
        "other_credits": -10, "tcs": 5,
    }, "UGVCL", "bill.pdf", [1])
    content = export_excel([record])
    values = load_workbook(BytesIO(content), data_only=True)
    formulas = load_workbook(BytesIO(content))
    sheet = values["Extracted Bills"]
    assert sheet["L2"].value == 0.25
    assert sheet["Q2"].value == "-"
    assert sheet["AN2"].value == 1100
    assert sheet["BE2"].value == -10
    assert sheet["BI2"].value == 1195
    assert sheet["BM2"].value == 11.95
    assert values["Summary"]["BI2"].value == 1195
    assert values["Summary"]["BI3"].value == 1195
    for tab in formulas:
        for row in tab:
            for cell in row:
                if cell.data_type == "f":
                    assert values[tab.title][cell.coordinate].value is not None
    # Re-evaluate after an input edit, including a zero denominator.
    formulas["Extracted Bills"]["I2"] = 0
    formulas["Extracted Bills"]["AB2"] = 1900
    changed = load_workbook(BytesIO(save_with_formula_results(formulas)), data_only=True)
    assert changed["Extracted Bills"]["L2"].value == "-"
    assert changed["Extracted Bills"]["AN2"].value == 2100
    assert changed["Summary"]["AN2"].value == 2100


def test_cache_rejects_unsupported_or_circular_formulas():
    workbook = load_workbook(BytesIO(export_excel([])))
    sheet = workbook["Extracted Bills"]
    sheet["A2"] = '=HYPERLINK("https://example.com")'
    with pytest.raises(ValueError, match="Unsupported"):
        save_with_formula_results(workbook)
    sheet["A2"] = "=A2"
    with pytest.raises(ValueError, match="Circular"):
        save_with_formula_results(workbook)
