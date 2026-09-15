"""High-level batch extraction orchestration."""

from dataclasses import dataclass

from bill_extractor.calculations import calculate_kwh_change, calculate_record, month_sort_key
from bill_extractor.document import extract_pages, segment_bills
from bill_extractor.models import BillRecord
from bill_extractor.providers import PARSERS
from bill_extractor.providers.base import ProviderParser
from bill_extractor.schema import empty_record
from bill_extractor.validation import validate


@dataclass(frozen=True)
class InputFile:
    name: str
    data: bytes


def _parser_for(text: str):
    return next((parser for parser in PARSERS if parser.matches(text)), None)


def _merge_related_records(records: list[BillRecord]) -> list[BillRecord]:
    """Combine a bill image and its separately uploaded adjustment page."""
    merged: list[BillRecord] = []
    by_identity: dict[tuple[str, str, str], BillRecord] = {}
    for record in records:
        customer = record.values.get("customer_id")
        month = record.values.get("billing_month")
        if record.provider == "Unknown" or not customer or not month:
            merged.append(record)
            continue
        key = (record.provider, str(customer), str(month))
        existing = by_identity.get(key)
        if existing is None:
            by_identity[key] = record
            merged.append(record)
            continue
        for field, value in record.values.items():
            if existing.values.get(field) is None and value is not None:
                existing.values[field] = value
        if record.filename not in existing.filename.split(" + "):
            existing.filename = f"{existing.filename} + {record.filename}"
        existing.pages = sorted(set(existing.pages + record.pages))
        existing.warnings.extend(warning for warning in record.warnings if warning not in existing.warnings)
    return merged


def extract_files(files: list[InputFile], use_ocr: bool = True) -> list[BillRecord]:
    records: list[BillRecord] = []
    for source in files:
        pages, document_warnings = extract_pages(source.data, source.name, use_ocr=use_ocr)
        for segment in segment_bills(pages):
            text = "\n".join(page.text for page in segment)
            parser = _parser_for(text)
            common_values = ProviderParser.parse_common(text)
            if parser:
                specific_values = parser.parse(text)
                values = {
                    key: specific_values.get(key)
                    if specific_values.get(key) is not None
                    else common_values.get(key)
                    for key in empty_record()
                }
            else:
                values = common_values
            record = BillRecord(
                values=values,
                provider=parser.name if parser else ProviderParser.detected_provider(text),
                filename=source.name,
                pages=[page.number for page in segment],
                warnings=[document_warnings[page.number] for page in segment if page.number in document_warnings],
            )
            if not text.strip():
                record.warnings.append("No text could be extracted from this bill.")
            elif parser is None:
                record.warnings.append(
                    "No provider-specific parser matched; only common bill fields were extracted."
                )
            records.append(record)

    records = _merge_related_records(records)
    for record in records:
        calculate_record(record.values)
        validate(record)
    records.sort(key=month_sort_key)
    calculate_kwh_change(records)
    return records
