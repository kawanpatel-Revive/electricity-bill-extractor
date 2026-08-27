# Changelog

## 2026-08-27

### Added
- Added a separate Other Debits field for bill adjustments.

### Changed
- Changed Torrent total energy charges to use the complete bill charge breakdown.

### Fixed
- Fixed Torrent extraction across legacy and OCR bill layouts.
- Fixed solar banking units, credits, deposit interest, and related debit adjustments.
- Fixed FPPAS charges being duplicated in fuel surcharge totals.

## 2026-08-21

### Added
- Added validation for mismatches between calculated adjustments and bill-printed adjustments.
- Added regression coverage for Torrent payable amounts and UGVCL S-21 solar adjustments.
- Added regression coverage for Streamlit preview table formatting.

### Fixed
- Fixed Torrent payable totals to retain the precise amount due from the bill.
- Fixed consumption-demand unit rate calculations to exclude demand charges.
- Fixed UGVCL S-21 solar setoff, surplus, and banking adjustment extraction.
- Fixed Streamlit preview tables to display mixed missing, numeric, and percentage values reliably.
