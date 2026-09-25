"""Dakshin Gujarat Vij Company (DGVCL) HT bill parser."""

import re
from math import floor

from bill_extractor.providers.base import ProviderParser
from bill_extractor.utils import NUMBER_TOKEN, normalized_month, parse_number


class DGVCLParser(ProviderParser):
    """Parse the tabular DGVCL HT-bill layout used by industrial accounts."""

    name = "DGVCL"

    def matches(self, text: str) -> bool:
        return bool(re.search(r"Dakshin\s+Gujarat\s+Vij\s+Company|\bDGVCL\b", text, re.I))

    @staticmethod
    def _number_row_after(text: str, header: str, minimum: int = 1) -> list[float]:
        match = re.search(header + r"[^\n]*\n((?:[^\n]*\n?){1,3})", text, re.I)
        if not match:
            return []
        for line in match.group(1).splitlines():
            numbers = [parse_number(token) for token in re.findall(NUMBER_TOKEN, line)]
            numbers = [number for number in numbers if number is not None]
            if len(numbers) >= minimum:
                return numbers
        return []

    @staticmethod
    def _line_amount(text: str, label: str) -> float | None:
        match = re.search(
            rf"^\s*{label}\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}%?\s+({NUMBER_TOKEN})\s*$",
            text,
            re.I | re.M,
        )
        return parse_number(match.group(1)) if match else None

    def parse(self, text: str) -> dict[str, str | float | None]:
        values = self.record()

        month = re.search(
            r"HT\s+B[IU]LL\s*[,.:]?\s+FOR\s+THE\s+MONTH\s+OF\s*:\s*([A-Z]{3,9}-\d{2,4})",
            text,
            re.I,
        )
        if month:
            month_value = normalized_month(month.group(1))
            values["billing_month"] = month_value.replace("JUI-", "JUL-") if month_value else None

        identity = re.search(
            rf"Consumer\s+No\s*:[^\n]*(?:\n[^\n]*){{0,2}}?\n\s*(\d{{4,}})\s+([A-Z][A-Z0-9-]+)\s+"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if identity:
            values["customer_id"] = identity.group(1)
            tariff = identity.group(2).upper()
            values["tariff_category"] = "HTP-1" if tariff in {"HTT-1", "HTF-1", "HTPI"} else tariff
            values["contract_demand"] = parse_number(identity.group(3))
            values["actual_max_demand"] = parse_number(identity.group(5))
            values["billing_demand"] = parse_number(identity.group(6))

        meter = re.search(
            r"Meter\s+No\.?\s*:[^\n]*\n\s*([A-Z][A-Z0-9/-]*\d[A-Z0-9/-]*)\b",
            text,
            re.I,
        )
        values["meter_number"] = meter.group(1) if meter else None

        supply = self._number_row_after(text, r"Supp\s+Voltage[^\n]*", 4)
        if len(supply) >= 3:
            kwh, kvah = supply[1], supply[2]
            printed_pf = supply[4] if len(supply) >= 6 and 0.5 <= supply[4] <= 1 else None
            if printed_pf is not None:
                values["average_power_factor"] = printed_pf
            elif kvah:
                values["average_power_factor"] = floor(min(kwh / kvah, 1.0) * 1000) / 1000

        consumption = self._number_row_after(text, r"A\.\s*Total\s+Units\s+B\.\s*Night\s+Units\s+C\.\s*TOU", 5)
        if len(consumption) >= 5:
            for key, value in zip(
                ("kwh_consumed", "night_units", "tou_kwh", "one_third_total_units", "night_concession_units"),
                consumption[:5],
            ):
                values[key] = value

        demand = re.search(rf"^\s*Tot\s+Deman[d]?\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})", text, re.I | re.M)
        values["demand_charges"] = parse_number(demand.group(1)) if demand else None
        values["energy_charges"] = self._line_amount(text, r"Energy\s+Charges")
        values["fuel_surcharge"] = self._line_amount(text, r"Fuel\s+(?:charge|surcharge)")
        values["power_factor_adjustment"] = self._line_amount(text, r"PF\s+(?:Adj(?:ustment)?|Rebate)")
        values["night_rebate"] = self._line_amount(text, r"Night\s+Rebate")
        values["ehv_rebate"] = self._line_amount(text, r"EHV\s+Rebate")
        values["tou_charges"] = self._line_amount(text, r"TOU")

        lines = text.splitlines()
        summary_start = next((i for i, line in enumerate(lines) if "SUMMARY OF CHARGES" in line.upper()), None)
        duty_start = next(
            (
                i
                for i, line in enumerate(lines)
                if (summary_start is None or i > summary_start)
                and re.search(r"Electr(?:icity|iclty)\s+Duty", line, re.I)
            ),
            None,
        )
        if summary_start is not None and duty_start is not None:
            for line in reversed(lines[summary_start + 1 : duty_start]):
                amounts = [parse_number(token) for token in re.findall(NUMBER_TOKEN, line)]
                amounts = [amount for amount in amounts if amount is not None]
                if len(amounts) >= 8:
                    summary_values = amounts[-9:] if len(amounts) >= 9 else amounts
                    if len(summary_values) == 9:
                        for key, amount in zip(
                            (
                                "demand_charges",
                                "energy_charges",
                                "fuel_surcharge",
                                "power_factor_adjustment",
                                "night_rebate",
                                "ehv_rebate",
                                "tou_charges",
                            ),
                            summary_values[:7],
                        ):
                            if values[key] is None:
                                values[key] = amount
                    values["total_consumption_charges"] = amounts[-1]
                    break

        payment_header_end = None
        for index in range(len(lines)):
            window = " ".join(lines[index : index + 3])
            if "Payment" in window and "Net Payable" in window and "Total Payable" in window:
                payment_header_end = next(
                    i for i in range(index, min(index + 3, len(lines))) if "Total Payable" in lines[i]
                )
                break
        if duty_start is not None and payment_header_end is not None:
            duty_numbers = []
            for line in lines[duty_start : payment_header_end + 1]:
                duty_numbers.extend(parse_number(token) for token in re.findall(NUMBER_TOKEN, line))
            duty_numbers = [number for number in duty_numbers if number is not None]
            if len(duty_numbers) >= 4:
                values["electricity_duty"] = duty_numbers[0]
                values["current_month_bill"] = duty_numbers[-2]
                values["outstanding_arrears"] = duty_numbers[-1]

        if payment_header_end is not None:
            for candidate in lines[payment_header_end + 1 : payment_header_end + 4]:
                before_date = re.split(r"\d{1,2}-\d{1,2}-\d{4}", candidate, maxsplit=1)[0]
                amounts = [parse_number(token) for token in re.findall(NUMBER_TOKEN, before_date)]
                amounts = [amount for amount in amounts if amount is not None]
                if len(amounts) >= 6:
                    values["delayed_payment_charges"] = amounts[0]
                    values["advance_adjustment"] = amounts[1]
                    if amounts[1] == 0:
                        values["calculated_adjustment"] = 0.0
                    values["net_payable"] = amounts[2]
                    values["tcs"] = amounts[3]
                    values["total_payable"] = amounts[4]
                    break

        return values
