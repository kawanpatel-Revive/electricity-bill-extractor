"""Provider adapter contract and conservative common bill extraction."""

from abc import ABC, abstractmethod
import re

from bill_extractor.schema import empty_record
from bill_extractor.utils import NUMBER_TOKEN, normalized_month, parse_number


class ProviderParser(ABC):
    name = "Unknown"

    @abstractmethod
    def matches(self, text: str) -> bool:
        """Return whether this adapter owns the supplied bill text."""

    @abstractmethod
    def parse(self, text: str) -> dict[str, str | float | None]:
        """Extract direct values into the canonical schema."""

    @staticmethod
    def record() -> dict[str, str | float | None]:
        return empty_record()

    @staticmethod
    def detected_provider(text: str) -> str:
        """Return a provider label when the bill identifies one explicitly."""
        company = re.search(
            r"\b(UGVCL|DGVCL|PGVCL|MGVCL)\b|"
            r"\b(Uttar|Dakshin|Paschim|Madhya)\s+Gujarat\s+Vij\s+Company",
            text,
            re.I,
        )
        if not company:
            return "Generic"
        if company.group(1):
            return company.group(1).upper()
        return {
            "uttar": "UGVCL",
            "dakshin": "DGVCL",
            "paschim": "PGVCL",
            "madhya": "MGVCL",
        }[company.group(2).lower()]

    @classmethod
    def parse_common(cls, text: str) -> dict[str, str | float | None]:
        """Extract fields shared by common industrial electricity-bill layouts.

        Patterns are deliberately label-driven. Provider adapters can overwrite
        these values with more precise interpretation of their own layouts.
        """
        values = empty_record()

        month = re.search(
            r"(?:HT\s+)?B[IU]LL\s+FOR\s+THE\s+MONTH\s+OF\s*:\s*([A-Z]{3,9}-\d{2,4})|"
            r"Billing\s+(?:Month|Period)\s*:?\s*([A-Z]{3,9}[\s,-]+\d{2,4})",
            text,
            re.I,
        )
        if month:
            values["billing_month"] = normalized_month(month.group(1) or month.group(2))

        identity = re.search(
            rf"Consumer\s+No\s*:[^\n]*\n\s*(\d{{4,}})\s+([A-Z][A-Z0-9-]+)\s+"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if identity:
            values["customer_id"] = identity.group(1)
            values["tariff_category"] = identity.group(2).upper()
            values["contract_demand"] = parse_number(identity.group(3))
            values["actual_max_demand"] = parse_number(identity.group(5))
            values["billing_demand"] = parse_number(identity.group(6))
        else:
            consumer = re.search(r"Consumer\s+No\.?\s*[:\-]?\s*(\d{4,})", text, re.I)
            tariff = re.search(r"Tariff\s+Category\s*[:\-]?\s*([A-Z][A-Z0-9-]+)", text, re.I)
            values["customer_id"] = consumer.group(1) if consumer else None
            values["tariff_category"] = tariff.group(1).upper() if tariff else None

        meter = re.search(
            r"Meter\s+No\.?\s*:[^\n]*(?:\n\s*)?([A-Z][A-Z0-9/-]*\d[A-Z0-9/-]*)\b",
            text,
            re.I,
        )
        values["meter_number"] = meter.group(1) if meter else None

        consumption = re.search(
            rf"A\.\s*Total\s+Units[^\n]*\n\s*({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+"
            rf"({NUMBER_TOKEN})\s+({NUMBER_TOKEN})\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if consumption:
            for key, group in zip(
                ("kwh_consumed", "night_units", "tou_kwh", "one_third_total_units", "night_concession_units"),
                range(1, 6),
            ):
                values[key] = parse_number(consumption.group(group))

        supply = re.search(
            rf"Supp\s+Voltage[^\n]*\n\s*{NUMBER_TOKEN}\s+({NUMBER_TOKEN})\s+{NUMBER_TOKEN}\s+"
            rf"{NUMBER_TOKEN}\s+({NUMBER_TOKEN})",
            text,
            re.I,
        )
        if supply:
            values["kwh_consumed"] = values["kwh_consumed"] or parse_number(supply.group(1))
            values["average_power_factor"] = parse_number(supply.group(2))

        def amount(pattern: str, group: int = 1) -> float | None:
            match = re.search(pattern, text, re.I | re.M)
            return parse_number(match.group(group)) if match else None

        values["demand_charges"] = amount(rf"^\s*Tot\s+Demand\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})")
        values["energy_charges"] = amount(
            rf"^\s*Energy\s+Charges\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["fuel_surcharge"] = amount(
            rf"^\s*Fuel\s+(?:charge|surcharge)\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["power_factor_adjustment"] = amount(
            rf"^\s*PF\s+[A-Z./]+(?:\s+[A-Z./]+)?\s+[^\n]*?({NUMBER_TOKEN})\s*$"
        )
        values["night_rebate"] = amount(
            rf"^\s*Night\s+Rebate\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )
        values["ehv_rebate"] = amount(
            rf"^\s*EHV\s+Rebate\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}%?\s+({NUMBER_TOKEN})"
        )
        values["tou_charges"] = amount(
            rf"^\s*TOU\s+{NUMBER_TOKEN}\s+{NUMBER_TOKEN}\s+({NUMBER_TOKEN})"
        )

        values["total_consumption_charges"] = amount(
            rf"Tot\s+Consumption(?:\s*\n|\s+)\s*({NUMBER_TOKEN})\s*\n\s*Charge"
        )
        summary = re.search(
            r"Demand\s+Charge\s+Energy\s+Charge[\s\S]{0,350}?Tot\s+Consumption\s+Charge\s*\n([^\n]+)",
            text,
            re.I,
        )
        if summary and values["total_consumption_charges"] is None:
            amounts = re.findall(NUMBER_TOKEN, summary.group(1))
            if amounts:
                values["total_consumption_charges"] = parse_number(amounts[-1])

        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "Electricity Duty" not in line or "Outstanding Arrears" not in line:
                continue
            for candidate in lines[index + 1 : index + 4]:
                amounts = [parse_number(item) for item in re.findall(NUMBER_TOKEN, candidate)]
                if len(amounts) >= 3:
                    values["electricity_duty"] = amounts[0]
                    values["current_month_bill"] = amounts[-2]
                    values["outstanding_arrears"] = amounts[-1]
                    break
            break

        for line in lines:
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

        return values
