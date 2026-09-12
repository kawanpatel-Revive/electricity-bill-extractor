# Electricity Bill Extractor

A provider-aware Streamlit tool that extracts the 58 columns in
`data/Angiplast_Bill_Analysis.xlsx` from industrial electricity bills. It
supports individual files, merged PDFs, native Excel export, and a controlled
OCR fallback for scanned pages.

## Supported providers

- UGVCL, including adjustment-detail and solar-banking pages
- Torrent Power industrial bills
- PGVCL selectable-text bills

Unknown layouts are returned for review instead of being silently interpreted
with another provider's rules.

## Setup

Python 3.10 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local address printed by Streamlit, normally
`http://localhost:8501`.

## OCR behavior

PyMuPDF extracts the embedded text layer first. Rasterized pages with less than
80 useful characters are sent to OCR; sparse selectable-text continuation pages
are retained without unnecessary OCR. The tool uses Tesseract when it is
available and automatically falls back to the bundled offline RapidOCR engine
otherwise. No external OCR executable is required for JPG, PNG, or scanned-PDF
uploads. Linux Streamlit deployments install the OpenCV `libGL` runtime declared
in `packages.txt`.

Photographs take longer than selectable-text PDFs because OCR runs locally.
For multi-page bills uploaded as separate images, matching provider, customer,
and billing-month pages are combined into one result row. This allows a main
UGVCL bill photograph and its adjustment-detail photograph to contribute to the
same extraction record.

## Output behavior

- One row is produced for each detected bill/month.
- The Excel sheet uses the same 58 headers and order as the reference workbook.
- Missing source values remain `None` internally and appear as `-` in the UI and Excel.
- Ratios and unit rates are calculated only when all required inputs exist.
- `% Increase in kWh` is a month-over-month calculation per customer.
- The Excel `Extraction Details` sheet lists provider, source file, pages, and warnings.
- Excel exports contain editable cell formulas following `Sample_Spreadsheet.xlsx`
  for ratios, solar units, energy charges, adjustments, payable totals, and unit
  rates. References follow the export's column order. Missing required inputs or
  zero denominators display `-`; optional missing charge components are ignored.
- The `Summary` sheet reproduces the sample's mixed SUM/AVERAGE row and separate
  units/payable totals for each customer. Formula results recalculate when opened
  in Excel. Cached formula results are also saved so previews and readers that
  do not calculate formulas can display the initial results.
- Excel charge ratios and consumption rates use calculated Total Energy/Consumption
  Charges, as in the sample. Formula Adv Adjustment includes wheeling charges and
  previous dues and excludes TCS; TCS is added once in Total Payable. Consequently,
  workbook calculations can differ from printed bill totals and the unchanged
  UI/JSON values. Source credit/debit amounts remain numeric inputs, including
  amounts that the sample entered as literal arithmetic.

The supplied reference workbook contains several broken `#REF!` formulas and a
small number of manually entered totals that differ from the source adjustment
lines. The extractor uses source bill values and implements deterministic
calculations rather than copying broken spreadsheet formulas.

## Architecture

```text
bill_extractor/
  document.py       text extraction, OCR fallback, bill segmentation
  providers/        isolated UGVCL, Torrent, and PGVCL adapters
  schema.py         canonical 58-field contract
  calculations.py   derived values
  validation.py     cross-field consistency checks
  service.py        batch orchestration
  export.py         Excel and JSON output
```

`extractor.py` retains the original nested API for backward compatibility. New
code should use `bill_extractor.service.extract_files`.

## Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

The regression suite checks the complete header contract, the 12-month merged
UGVCL sample, multi-row solar adjustments, Torrent Power extraction, PGVCL
compatibility, calculations, and Excel output.
