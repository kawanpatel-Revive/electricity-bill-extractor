"""Streamlit interface for batch electricity-bill extraction."""

import streamlit as st

from bill_extractor.export import export_excel, export_json
from bill_extractor.presentation import display_dataframe
from bill_extractor.service import InputFile, extract_files


st.set_page_config(page_title="Electricity Bill Extractor", page_icon="⚡", layout="wide")
st.title("Electricity Bill Extractor")
st.caption(
    "Extract the reference spreadsheet fields from electricity bills using detailed "
    "provider parsers and a common-field fallback. Upload individual bills or merged PDFs."
)

uploaded_files = st.file_uploader(
    "Choose electricity bills",
    type=["pdf", "jpg", "jpeg", "png"],
    accept_multiple_files=True,
)
use_ocr = st.checkbox(
    "Use OCR for scanned pages",
    value=True,
    help="OCR requires Tesseract to be installed on the computer running this tool.",
)

if uploaded_files:
    try:
        sources = [InputFile(file.name, file.getvalue()) for file in uploaded_files]
        with st.spinner("Extracting bill data..."):
            records = extract_files(sources, use_ocr=use_ocr)

        if not records:
            st.error("No bills were found in the uploaded files.")
        else:
            st.success(f"Extracted {len(records)} bill(s) from {len(uploaded_files)} file(s).")
            st.dataframe(display_dataframe(records), use_container_width=True, hide_index=True)

            left, right = st.columns(2)
            with left:
                st.download_button(
                    "Download Excel",
                    export_excel(records),
                    file_name="electricity_bill_extraction.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with right:
                st.download_button(
                    "Download JSON",
                    export_json(records),
                    file_name="electricity_bill_extraction.json",
                    mime="application/json",
                    use_container_width=True,
                )

            records_with_warnings = [record for record in records if record.warnings]
            if records_with_warnings:
                with st.expander(f"Review warnings ({len(records_with_warnings)})"):
                    for record in records_with_warnings:
                        st.markdown(
                            f"**{record.filename}, pages {', '.join(map(str, record.pages))}:** "
                            + " | ".join(record.warnings)
                        )
    except Exception as exc:
        st.error(f"Could not process the uploaded bills: {exc}")
