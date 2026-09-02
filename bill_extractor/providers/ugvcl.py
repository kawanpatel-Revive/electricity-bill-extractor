"""Uttar Gujarat Vij Company (UGVCL) bill parser."""

import re

from bill_extractor.providers.base import ProviderParser
from bill_extractor.utils import NUMBER_TOKEN, normalized_month, parse_number


class UGVCLParser(ProviderParser):
    name = "UGVCL"

    def matches(self, text: str) -> bool:
        return bool(re.search(r"Uttar\s+Gujarat\s+Vij\s+Company|\bUGVCL\b", text, re.I))

    def parse(self, text: str) -> dict[str, str | float | None]:
        values = self.record()
        self._parse_identity(text, values)
        self._parse_consumption(text, values)
        self._parse_charges(text, values)
        self._parse_adjustments(text, values)
        return values

    @staticmethod
    def _parse_identity(text: str, values: dict[str, str | float | None]) -> None:
        bill_month = re.search(r"HT\s+BILL\s+FOR\s+THE\s+MONTH\s+OF\s*:\s*([A-Z]{3,9}-\d{4})", text, re.I)
        report_month = re.search(r"Adjustment\s+Details\s+Report\s+for\s+([A-Z]{3,9}-\d{4})", text, re.I)
        month = report_month if report_month and "CALCULATION OF CHARGES" not in text.upper() else bill_month
        values["billing_month"] = normalized_month(month.group(1)) if month else None

        identity = re.search(
            rf"Consumer\s+No:[\s\S]{{0,260}}?\n\s*(\d{{4,}})\s+([A-Z][A-Z0-9-]+)\s+"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if identity:
            values["customer_id"] = identity.group(1)
            values["tariff_category"] = identity.group(2)
            values["contract_demand"] = parse_number(identity.group(3))
            values["actual_max_demand"] = parse_number(identity.group(5))
            values["billing_demand"] = parse_number(identity.group(6))
        else:
            row = re.search(rf"^\s*(\d{{4,}})\s+([A-Z]*TP[-A-Z0-9]+)\s+(.+)$", text, re.I | re.M)
            if row:
                values["customer_id"] = row.group(1)
                tariff = row.group(2).upper()
                values["tariff_category"] = "HTP-I" if re.fullmatch(r"[A-Z]*TP-[1I]", tariff) else tariff
                numbers = [parse_number(item) for item in re.findall(NUMBER_TOKEN, row.group(3))]
                if len(numbers) >= 4:
                    values["contract_demand"] = numbers[0]
                    values["actual_max_demand"] = numbers[2]
                    billing_demand = numbers[3]
                    if billing_demand is not None and billing_demand < 10 <= numbers[1]:
                        billing_demand *= 100
                    values["billing_demand"] = billing_demand

        if values["customer_id"] is None:
            customer = re.search(r"Consumer\s+No\s*:\s*(\d{4,})", text, re.I)
            if customer:
                values["customer_id"] = customer.group(1)
            else:
                header_row = re.search(
                    r"Consumer\s+No:[\s\S]{0,300}?\n\s*(\d{4,})\s+([A-Z]*TP[-A-Z0-9]+)",
                    text,
                    re.I,
                )
                if header_row:
                    values["customer_id"] = header_row.group(1)
                    tariff = header_row.group(2).upper()
                    values["tariff_category"] = "HTP-I" if re.fullmatch(r"[A-Z]*TP-[1I]", tariff) else tariff

        meter = re.search(
            r"Meter\s+No:[\s\S]{0,320}?\n\s*([A-Z][A-Z0-9/-]*\d[A-Z0-9/-]*)\b",
            text,
            re.I,
        )
        if meter:
            values["meter_number"] = meter.group(1)

    @staticmethod
    def _parse_consumption(text: str, values: dict[str, str | float | None]) -> None:
        summary = re.search(
            rf"Supp\s+Voltage[^\n]*\n\s*{NUMBER_TOKEN}\s+({NUMBER_TOKEN})\s+{NUMBER_TOKEN}\s+"
            rf"{NUMBER_TOKEN}\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if summary:
            values["kwh_consumed"] = parse_number(summary.group(1))
            power_factor = parse_number(summary.group(2))
            if power_factor is not None and power_factor > 100:
                power_factor /= 1000
            values["average_power_factor"] = power_factor
        else:
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if "Supp Voltage" not in line:
                    continue
                for candidate in lines[index + 1 : index + 3]:
                    numbers = [parse_number(item) for item in re.findall(NUMBER_TOKEN, candidate)]
                    if len(numbers) >= 5:
                        values["kwh_consumed"] = numbers[-5]
                        power_factor = numbers[-2]
                        if power_factor is not None and power_factor > 100:
                            power_factor /= 1000
                        values["average_power_factor"] = power_factor
                        break
                break

        consumption = re.search(
            rf"A\.Total\s+Units[\s\S]{{0,300}}?\n\s*({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if consumption:
            values["kwh_consumed"] = parse_number(consumption.group(1))
            values["night_units"] = parse_number(consumption.group(2))
            values["tou_kwh"] = parse_number(consumption.group(3))
            values["one_third_total_units"] = parse_number(consumption.group(4))
            values["night_concession_units"] = parse_number(consumption.group(5))
        else:
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if not ("A.Total Units" in line and "B.Night Units" in line):
                    continue
                for candidate in lines[index + 1 : index + 3]:
                    numbers = [parse_number(item) for item in re.findall(NUMBER_TOKEN, candidate)]
                    if len(numbers) >= 5:
                        values["kwh_consumed"] = numbers[0]
                        values["night_units"] = numbers[1]
                        values["tou_kwh"] = numbers[2]
                        values["one_third_total_units"] = numbers[3]
                        values["night_concession_units"] = numbers[4]
                        break
                break

    @staticmethod
    def _amount_after_label(text: str, label: str, amount_group: int = 1) -> float | None:
        match = re.search(label, text, re.I | re.M)
        return parse_number(match.group(amount_group)) if match else None

    def _parse_charges(self, text: str, values: dict[str, str | float | None]) -> None:
        values["demand_charges"] = self._amount_after_label(
            text, rf"^\s*Tot\s+Demand\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["excess_demand_charges"] = self._amount_after_label(
            text, rf"^\s*Excess\s+DMD(?:\s+{NUMBER_TOKEN}){{0,2}}\s*({NUMBER_TOKEN})?\s*$"
        )
        if values["excess_demand_charges"] is None and re.search(r"^\s*Excess\s+DMD\s*$", text, re.I | re.M):
            values["excess_demand_charges"] = 0.0
        values["energy_charges"] = self._amount_after_label(
            text, rf"^\s*Energy\s+Charges\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        if values["energy_charges"] is None:
            energy_line = re.search(r"^\s*Energy\s+Charges\s+([^\n]+)$", text, re.I | re.M)
            if energy_line:
                amounts = [parse_number(item) for item in re.findall(NUMBER_TOKEN, energy_line.group(1))]
                if len(amounts) >= 2:
                    values["energy_charges"] = amounts[1]
        values["fuel_surcharge"] = self._amount_after_label(
            text, rf"^\s*Fuel\s+charge\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["power_factor_adjustment"] = self._amount_after_label(
            text, rf"^\s*PF\s+(?:Rebate|Penalty|Adj(?:ustment)?)\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}%?\s+({NUMBER_TOKEN})"
        )
        pf_line = re.search(r"^\s*PF\s+(?:Rebate|Penalty|Adj(?:ustment)?)\s+([^\n]+)$", text, re.I | re.M)
        if pf_line:
            amounts = [parse_number(item) for item in re.findall(NUMBER_TOKEN, pf_line.group(1))]
            if amounts:
                values["power_factor_adjustment"] = amounts[-1]
        values["night_rebate"] = self._amount_after_label(
            text, rf"^\s*Night\s+Rebate\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["ehv_rebate"] = self._amount_after_label(
            text, rf"^\s*EHV\s+Rebate\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}%?\s+({NUMBER_TOKEN})"
        )
        values["tou_charges"] = self._amount_after_label(
            text, rf"^\s*TOU\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["total_consumption_charges"] = self._amount_after_label(
            text, rf"Tot\s+Consumption(?:\s*\n|\s+)\s*({NUMBER_TOKEN})\s*\n\s*Charge"
        )
        if values["total_consumption_charges"] is None:
            summary = re.search(
                r"Demand\s+Charge\s+Energy\s+Charge[\s\S]{0,300}?Tot\s+Consumption\s+Charge\s*\n([^\n]+)",
                text,
                re.I,
            )
            if summary:
                amounts = re.findall(NUMBER_TOKEN, summary.group(1))
                if amounts:
                    values["total_consumption_charges"] = parse_number(amounts[-1])
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if not (re.search(r"Electricity\s+Duty", line, re.I) and re.search(r"Outstanding\s+Arrears", line, re.I)):
                continue
            for candidate in lines[index + 1 : index + 4]:
                amounts = [parse_number(item) for item in re.findall(NUMBER_TOKEN, candidate)]
                if len(amounts) >= 3:
                    values["electricity_duty"] = amounts[0]
                    values["current_month_bill"] = amounts[-2]
                    values["outstanding_arrears"] = amounts[-1]
                    values["previous_dues"] = 0.0
                    values["wheeling_charges"] = 0.0
                    break
            break

        for line in text.splitlines():
            date = re.search(r"\d{1,2}-\d{1,2}-\d{4}", line)
            if not date:
                continue
            amounts = [parse_number(item) for item in re.findall(NUMBER_TOKEN, line[: date.start()])]
            if len(amounts) >= 6:
                (
                    values["delayed_payment_charges"],
                    values["advance_adjustment"],
                    values["net_payable"],
                    values["tcs"],
                    values["total_payable"],
                    _,
                ) = amounts[-6:]
                break

    @staticmethod
    def _parse_adjustments(text: str, values: dict[str, str | float | None]) -> None:
        # Newer UGVCL PDFs position the final word of some descriptions after
        # the amount/remarks columns in extracted reading order. Normalize
        # those visually single-row entries before applying the row parser.
        wrapped_entry = re.compile(
            rf"^\s*(Credit\s+(?:Board|ED)|Debit\s+(?:Banking|Board))\s*\n\s*"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+([^\n]+)\n\s*(Charges?)\s*$",
            re.I | re.M,
        )
        text = wrapped_entry.sub(
            lambda match: (
                f"{match.group(1)} {match.group(5)} {match.group(2)} "
                f"{match.group(3)} {match.group(4)}"
            ),
            text,
        )

        def adjustment_units(remarks: str, fallback: float) -> float:
            multiplied = re.search(r"\(\s*(\d[\d,]*)\s*[Xx×]", remarks)
            if multiplied:
                return parse_number(multiplied.group(1)) or fallback
            rated_units = re.search(r"\b(\d[\d,]*(?:\.\d+)?)\s*@", remarks)
            if rated_units:
                return parse_number(rated_units.group(1)) or fallback
            unit_values = re.findall(r"\d[\d,]*(?:\.\d+)?", remarks)
            return parse_number(unit_values[-1]) if unit_values else fallback

        solar_setoff_amount = 0.0
        solar_setoff_units = 0.0
        solar_export_amount = 0.0
        solar_export_units = 0.0
        banking_amount = 0.0
        banking_units = 0.0
        other_credits = 0.0
        other_debits = 0.0
        electricity_duty_credits = 0.0
        tou_charge_credits = 0.0
        tds_credits = 0.0
        security_interest = 0.0
        debit_tcs = 0.0
        found_adjustment = False
        has_solar_unit_credit_layout = "SOLAR UNIT CREDIT - BOARD CHARGE AMOUNT" in text.upper()

        entry = re.compile(
            rf"^\s*(Credit\s+Board\s+Charges|Credit\s+ED\s+Charges|Credit\s+TDS|"
            rf"Cedit\s+Fuel\s+Surcharge|Credit\s+Fuel\s+Surcharge|Credit\s+JV|"
            rf"Debit\s+Banking\s+Charges?|Debit\s+Electricity\s+Duty|"
            rf"Debit\s+Board\s+Charges?|Debit\s+Fuel\s+Surcharge|Debit\s+TCS)\s+"
            rf"({NUMBER_TOKEN})\s+"
            rf"(?:[A-Z]{{1,4}}\s+)?({NUMBER_TOKEN})\s+(.+)$",
            re.I,
        )
        for line in text.splitlines():
            match = entry.match(line)
            if not match:
                continue
            found_adjustment = True
            description, amount_text, units_text, remarks = match.groups()
            amount = parse_number(amount_text) or 0.0
            units = parse_number(units_text) or 0.0
            upper_remarks = remarks.upper()
            is_s21_setoff = bool(re.search(r"\bS-?21\s+CR\s+BC\b", upper_remarks))
            is_s21_surplus = bool(re.search(r"\bS-?21\s+CR\s+SURPLUS\b", upper_remarks))
            is_s21_banking = "S-21 DR" in upper_remarks and (
                "BANKING" in upper_remarks or "BNAKING" in upper_remarks
            )
            description_lower = description.lower()
            is_credit_board = description_lower.startswith("credit board")
            is_credit_ed = description_lower.startswith("credit ed")
            is_credit_tds = description_lower.startswith("credit tds")
            is_tou_credit = "11 AM TO 3 PM" in upper_remarks or "TOU" in upper_remarks
            is_solar_setoff = (
                "SOLAR SETOFF" in upper_remarks
                or "SOLAR UNIT CREDIT" in upper_remarks
                or re.search(r"\bSOLAR\s+(?:BOARD\s+CHARGE\s+|ELEC\.?\s+DUTY\s+)?ADJ\b", upper_remarks)
                or re.fullmatch(r"\s*SOLAR\s+[A-Z]{3,9}\s+\d{2,4}\s*", upper_remarks)
                or is_s21_setoff
            )
            if is_credit_ed:
                electricity_duty_credits -= amount
            elif is_credit_tds:
                if has_solar_unit_credit_layout and "LESS CREDIT GIVEN TO CONSUMER" in upper_remarks:
                    other_credits -= amount
                else:
                    tds_credits -= amount
            elif is_credit_board and is_solar_setoff:
                solar_setoff_amount += amount
                solar_setoff_units += units
            elif is_credit_board and is_tou_credit:
                tou_charge_credits -= amount
            elif "SOLAR SURPLUS" in upper_remarks or "SOLAR SPU" in upper_remarks or is_s21_surplus:
                solar_export_amount += amount
                solar_export_units += adjustment_units(remarks, units)
            elif "SOLAR B.U." in upper_remarks or "SOLAR BANKING" in upper_remarks or is_s21_banking:
                banking_amount += amount
                banking_units += adjustment_units(remarks, units)
            elif "SD INTEREST" in upper_remarks:
                security_interest += amount
            elif description_lower.startswith("debit tcs"):
                debit_tcs += amount
            elif description_lower.startswith(("credit", "cedit")):
                other_credits -= amount
            elif description_lower.startswith("debit"):
                other_debits += amount

        if not found_adjustment:
            return
        values["solar_setoff_units"] = solar_setoff_units
        values["solar_setoff_credit"] = -solar_setoff_amount if solar_setoff_amount else 0.0
        values["solar_export_units"] = solar_export_units
        values["solar_credit"] = -solar_export_amount if solar_export_amount else 0.0
        values["solar_banking_units"] = banking_units
        values["solar_banking_charges"] = banking_amount
        values["electricity_duty_credits"] = electricity_duty_credits
        values["tou_charge_credits"] = tou_charge_credits
        values["tds_credits"] = tds_credits
        values["other_debits"] = other_debits
        values["other_credits"] = other_credits
        values["security_deposit_interest"] = -security_interest if security_interest else 0.0
        if debit_tcs:
            values["tcs"] = debit_tcs
