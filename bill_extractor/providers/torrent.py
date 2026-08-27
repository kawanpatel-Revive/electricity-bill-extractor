"""Torrent Power industrial bill parser."""

import re

from bill_extractor.providers.base import ProviderParser
from bill_extractor.utils import NUMBER_TOKEN, normalized_month, parse_number, sum_known


class TorrentParser(ProviderParser):
    name = "Torrent Power"

    def matches(self, text: str) -> bool:
        return bool(re.search(r"Torrent\s+Power", text, re.I))

    def parse(self, text: str) -> dict[str, str | float | None]:
        values = self.record()
        self._parse_header(text, values)
        self._parse_meter(text, values)
        self._parse_charges(text, values)
        self._parse_solar(text, values)
        return values

    @staticmethod
    def _find(text: str, pattern: str, group: int = 1) -> str | None:
        match = re.search(pattern, text, re.I | re.M)
        return " ".join(match.group(group).split()) if match else None

    def _parse_header(self, text: str, values: dict[str, str | float | None]) -> None:
        contract = self._find(text, rf"CONTRACT\s+DEMAND[\s\S]{{0,100}}?({NUMBER_TOKEN})\s*KW")
        month_tariff = re.search(r"([A-Z]{3,9}\s+\d{4})\s+([A-Z]+\d+)\b", text, re.I)
        header_text = "\n".join(text.splitlines()[:40])
        billing_line = next(
            (line for line in text.splitlines() if re.search(rf"{NUMBER_TOKEN}\s*KW", line) and re.search(r"\d{1,2}/\d{1,2}/\d{2}", line)),
            "",
        )
        billing_match = re.search(rf"({NUMBER_TOKEN})\s*KW", billing_line)
        customer_matches = re.findall(r"\b\d{8,}\b", billing_line)
        power_factor = self._find(
            text,
            rf"Registered\s+Mobile[^\n]*?\s({NUMBER_TOKEN})\s+\d{{1,2}}/\d{{1,2}}/\d{{2}}",
        )
        values["contract_demand"] = parse_number(contract)
        values["billing_demand"] = parse_number(billing_match.group(1)) if billing_match else None
        values["customer_id"] = customer_matches[-1] if customer_matches else None
        if month_tariff:
            values["billing_month"] = normalized_month(month_tariff.group(1))
            values["tariff_category"] = month_tariff.group(2).upper()
        else:
            # OCR commonly places the tariff on the BILLING MONTH line and the
            # actual month on the following address line.
            month = self._find(
                header_text,
                r"BILLING\s+MONTH[\s\S]{0,160}?([A-Z]{3,9}\s+\d{4})",
            )
            tariff = self._find(header_text, r"BILLING\s+MONTH\s+([A-Z]+\s*\d+)\b")
            values["billing_month"] = normalized_month(month)
            values["tariff_category"] = re.sub(r"\s+", "", tariff).upper() if tariff else None
        pf = parse_number(power_factor)
        values["average_power_factor"] = pf / 100 if pf is not None and pf > 1 else pf

    def _parse_meter(self, text: str, values: dict[str, str | float | None]) -> None:
        values["meter_number"] = self._find(text, r"Meter\s+No\.?\s*:\s*([A-Z0-9/-]+)")
        units = re.search(
            rf"^\s*Units\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I | re.M,
        )
        if units:
            values["actual_max_demand"] = parse_number(units.group(1))
            values["kwh_consumed"] = parse_number(units.group(2))
            values["tou_kwh"] = parse_number(units.group(3))
            values["night_units"] = parse_number(units.group(5))
            values["night_concession_units"] = parse_number(units.group(5))

    def _amount(self, text: str, label: str) -> float | None:
        value = self._find(text, rf"^\s*{label}\s+({NUMBER_TOKEN})(?:\s|$)")
        return parse_number(value)

    def _parse_charges(self, text: str, values: dict[str, str | float | None]) -> None:
        values["energy_charges"] = self._amount(text, r"Energy\s+charges(?:\s*\(A\))?")
        values["demand_charges"] = self._amount(
            text, r"Fixed\s+demand\s+charges(?:\s*\(B\))?"
        )
        values["excess_demand_charges"] = self._amount(text, r"Excess\s+demand\s+charges")
        values["base_fppas"] = self._amount(text, r"Base\s+FPPAS[^\n]*\(C\)")
        if values["base_fppas"] is None:
            # Bills issued before the FPPAS split print the entire base amount
            # as a single FPPPA charge in paise per unit.
            values["base_fppas"] = self._amount(
                text,
                rf"FPPPA\s+charges\s*@\s*{NUMBER_TOKEN}\s*\(paise/unit\)",
            )
        additional_fppas_match = re.search(
            rf"FPPAS\s+charges\s*@\s*({NUMBER_TOKEN})\s*%\s+of\s*"
            rf"\(A\s*\+\s*B\s*\+\s*C\)\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if additional_fppas_match:
            percentage = parse_number(additional_fppas_match.group(1))
            values["fppas_charges"] = parse_number(additional_fppas_match.group(2))
            values["fppas_percent"] = percentage / 100 if percentage is not None else None
        # Torrent exposes base and additional FPPAS separately. Keep the legacy
        # Fuel Surcharge columns empty so exports do not count the same charge twice.
        values["fuel_surcharge"] = None
        values["tou_charges"] = self._amount(text, r"TOU\s+charges")
        values["power_factor_adjustment"] = self._amount(text, r"Power\s+Factor\s+adjustment\s+charges")
        values["night_rebate"] = self._amount(text, r"NTC\s+rebate")
        total_energy = self._find(text, rf"Total\s+energy\s+charges\s+({NUMBER_TOKEN})")
        values["total_consumption_charges"] = parse_number(total_energy)
        required_components = (
            values["energy_charges"],
            values["demand_charges"],
            values["base_fppas"],
        )
        has_additional_fppas = bool(re.search(r"FPPAS\s+charges\s*@\s*[^\n]*%", text, re.I))
        if all(component is not None for component in required_components) and (
            not has_additional_fppas or values["fppas_charges"] is not None
        ):
            calculated_total = sum_known(
                values["energy_charges"],
                values["demand_charges"],
                values["excess_demand_charges"],
                values["base_fppas"],
                values["fppas_charges"],
                values["power_factor_adjustment"],
                values["night_rebate"],
                values["ehv_rebate"],
                values["tou_charges"],
            )
            values["total_energy_charges"] = (
                round(calculated_total, 2) if calculated_total is not None else None
            )
        duty = self._find(
            text,
            rf"Total\s+government\s+duty\s*@\s*{NUMBER_TOKEN}\s*%\s+({NUMBER_TOKEN})",
        )
        values["electricity_duty"] = parse_number(duty)
        banking_rate_match = re.search(
            rf"Banking\s+charges[^\n]*?@\s*(?:Rs\.?\s*)?({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if banking_rate_match:
            banking_rate = parse_number(banking_rate_match.group(1))
            values["solar_banking_charges"] = parse_number(banking_rate_match.group(2))
            if banking_rate not in (None, 0) and values["solar_banking_charges"] is not None:
                banking_units = float(values["solar_banking_charges"]) / float(banking_rate)
                values["solar_banking_units"] = (
                    round(banking_units) if abs(banking_units - round(banking_units)) < 0.01 else banking_units
                )
        total_credit = self._amount(text, r"Credit")
        solar_credit_note = self._find(text, rf"Credit\s+of\s+Rs\.?\s*({NUMBER_TOKEN})")
        solar_credit = parse_number(solar_credit_note)
        if solar_credit is None:
            solar_credit = total_credit
        values["solar_credit"] = -abs(solar_credit) if solar_credit is not None else None
        if total_credit is not None and solar_credit is not None:
            other_credit = round(abs(total_credit) - abs(solar_credit), 2)
            if other_credit > 0.01:
                values["other_credits"] = -other_credit
        values["previous_dues"] = self._amount(text, r"Previous\s+dues")
        values["other_debits"] = self._amount(text, r"Other\s+debit")
        deposit_interest = self._find(
            text,
            rf"Security\s+Deposit\s+Interest\s+of\s+Rs\.?\s*({NUMBER_TOKEN})",
        )
        if deposit_interest is not None:
            values["security_deposit_interest"] = -abs(parse_number(deposit_interest))
        deposit_tds = self._find(
            text,
            rf"TDS\s+of\s+Rs\.?\s*({NUMBER_TOKEN})[^\n]*credited\s+and\s+adjusted",
        )
        if deposit_tds is not None:
            values["other_debits"] = sum_known(
                values["other_debits"], parse_number(deposit_tds)
            )
        values["wheeling_charges"] = self._amount(text, r"Wheeling\s+charges")
        values["delayed_payment_charges"] = self._amount(text, r"Delay\s+payment\s+charges")
        values["net_payable"] = self._amount(text, r"Amount\s+due")
        bill_amount = self._find(
            text,
            rf"B\s*I\s*L\s*L\s+A\s*M\s*O\s*U\s*N\s*T\s*:\s*R\s*({NUMBER_TOKEN})",
        )
        values["total_payable"] = (
            values["net_payable"]
            if values["net_payable"] is not None
            else parse_number(bill_amount)
        )
        values["current_month_bill"] = sum_known(
            values["total_consumption_charges"], values["electricity_duty"]
        )

    @staticmethod
    def _parse_solar(text: str, values: dict[str, str | float | None]) -> None:
        note = re.search(
            rf"Solar\s+generation\s+units\s+are\s*:\s*({NUMBER_TOKEN})\s*,\s*Net\s+billed\s+units-\s*({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if note:
            values["solar_generation_units"] = parse_number(note.group(1))
            values["solar_net_billed_units"] = parse_number(note.group(2))
        setoff = re.search(rf"Solar\s+S\w*off\s+Units\s+({NUMBER_TOKEN})", text, re.I)
        if setoff:
            values["solar_setoff_units"] = parse_number(setoff.group(1))
        export = re.search(rf"for\s+({NUMBER_TOKEN})\s+excess\s+Solar", text, re.I)
        if export:
            values["solar_export_units"] = parse_number(export.group(1))
        if values["solar_generation_units"] is not None and values["solar_banking_units"] is not None:
            values["solar_export_units"] = (
                float(values["solar_generation_units"]) - float(values["solar_banking_units"])
            )
        elif values["solar_generation_units"] is not None and values["solar_export_units"] is not None:
            values["solar_banking_units"] = (
                float(values["solar_generation_units"]) - float(values["solar_export_units"])
            )
