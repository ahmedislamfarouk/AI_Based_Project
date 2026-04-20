import os
import json
import base64
import re
from pathlib import Path
from typing import Optional
import streamlit as st
from groq import Groq
from PIL import Image
import pdfplumber
import io

GROQ_API_KEY = ""

client = Groq(api_key=GROQ_API_KEY)

EXTRACTION_PROMPT = """You are an expert invoice parser. Extract all key information from the invoice text/content below.

Return ONLY a valid JSON object with these fields (use null for missing fields):
{{
  "invoice_number": "string or null",
  "invoice_date": "string or null",
  "due_date": "string or null",
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "vendor_email": "string or null",
  "vendor_phone": "string or null",
  "client_name": "string or null",
  "client_address": "string or null",
  "line_items": [
    {{
      "description": "string",
      "quantity": number_or_null,
      "unit_price": number_or_null,
      "total": number_or_null
    }}
  ],
  "subtotal": number_or_null,
  "tax_rate": number_or_null,
  "tax_amount": number_or_null,
  "discount": number_or_null,
  "total_amount": number_or_null,
  "currency": "string or null",
  "payment_terms": "string or null",
  "payment_method": "string or null",
  "notes": "string or null"
}}

Invoice content:
{content}

Return only the JSON, no explanation."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def extract_text_from_image(file_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(file_bytes))
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    b64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                    {
                        "type": "text",
                        "text": "Please transcribe all text visible in this invoice image. Include every number, label, and piece of text exactly as shown.",
                    },
                ],
            }
        ],
        max_tokens=2000,
    )
    return response.choices[0].message.content


def parse_invoice_with_llm(content: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(content=content)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return json.loads(raw)


def validate_invoice(data: dict) -> list[str]:
    issues = []

    required = ["invoice_number", "invoice_date", "vendor_name", "total_amount"]
    for field in required:
        if not data.get(field):
            issues.append(f"Missing required field: {field}")

    line_items = data.get("line_items", [])
    if line_items:
        computed_subtotal = sum(
            item.get("total") or 0
            for item in line_items
            if item.get("total") is not None
        )
        reported_subtotal = data.get("subtotal")
        if reported_subtotal is not None and abs(computed_subtotal - reported_subtotal) > 0.01:
            issues.append(
                f"Subtotal mismatch: line items sum to {computed_subtotal:.2f} but reported subtotal is {reported_subtotal:.2f}"
            )

        for i, item in enumerate(line_items, 1):
            qty = item.get("quantity")
            price = item.get("unit_price")
            total = item.get("total")
            if qty is not None and price is not None and total is not None:
                expected = round(qty * price, 2)
                if abs(expected - total) > 0.01:
                    issues.append(
                        f"Line item {i} ({item.get('description', 'unknown')}): qty × price = {expected:.2f} but total = {total:.2f}"
                    )

    subtotal = data.get("subtotal") or 0
    tax = data.get("tax_amount") or 0
    discount = data.get("discount") or 0
    total = data.get("total_amount")
    if subtotal and total:
        expected_total = round(subtotal + tax - discount, 2)
        if abs(expected_total - total) > 0.01:
            issues.append(
                f"Total mismatch: subtotal ({subtotal}) + tax ({tax}) - discount ({discount}) = {expected_total:.2f} but reported total is {total:.2f}"
            )

    return issues


def format_report(data: dict, issues: list[str]) -> str:
    currency = data.get("currency") or ""
    lines = [
        "=" * 55,
        "           INVOICE PROCESSING REPORT",
        "=" * 55,
        f"  Invoice Number : {data.get('invoice_number') or 'N/A'}",
        f"  Invoice Date   : {data.get('invoice_date') or 'N/A'}",
        f"  Due Date       : {data.get('due_date') or 'N/A'}",
        "",
        "  VENDOR",
        f"    Name    : {data.get('vendor_name') or 'N/A'}",
        f"    Address : {data.get('vendor_address') or 'N/A'}",
        f"    Email   : {data.get('vendor_email') or 'N/A'}",
        f"    Phone   : {data.get('vendor_phone') or 'N/A'}",
        "",
        "  CLIENT",
        f"    Name    : {data.get('client_name') or 'N/A'}",
        f"    Address : {data.get('client_address') or 'N/A'}",
        "",
        "  LINE ITEMS",
        f"  {'Description':<30} {'Qty':>5} {'Unit':>10} {'Total':>10}",
        "  " + "-" * 57,
    ]
    for item in data.get("line_items") or []:
        desc = (item.get("description") or "")[:30]
        qty = str(item.get("quantity") or "")
        price = f"{item.get('unit_price'):.2f}" if item.get("unit_price") is not None else ""
        total = f"{item.get('total'):.2f}" if item.get("total") is not None else ""
        lines.append(f"  {desc:<30} {qty:>5} {price:>10} {total:>10}")

    lines += [
        "  " + "-" * 57,
        f"  {'Subtotal':<45} {currency} {data.get('subtotal') or '':>8}",
        f"  {'Tax':<45} {currency} {data.get('tax_amount') or '':>8}",
        f"  {'Discount':<45} {currency} {data.get('discount') or '':>8}",
        f"  {'TOTAL':<45} {currency} {data.get('total_amount') or '':>8}",
        "",
        f"  Payment Terms  : {data.get('payment_terms') or 'N/A'}",
        f"  Payment Method : {data.get('payment_method') or 'N/A'}",
        f"  Notes          : {data.get('notes') or 'N/A'}",
        "",
    ]

    if issues:
        lines += ["  VALIDATION ISSUES", "  " + "-" * 53]
        for issue in issues:
            lines.append(f"  ⚠  {issue}")
    else:
        lines.append("  ✓  All validation checks passed.")

    lines.append("=" * 55)
    return "\n".join(lines)


def process_invoice(file_bytes: bytes, filename: str) -> tuple[dict, list[str], str]:
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        content = extract_text_from_pdf(file_bytes)
        if not content.strip():
            raise ValueError("Could not extract text from PDF. It may be a scanned image PDF.")
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
        content = extract_text_from_image(file_bytes)
    elif ext == ".txt":
        content = file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if len(content.strip()) < 20:
        raise ValueError("Extracted content is too short — the document may be empty or unreadable.")

    data = parse_invoice_with_llm(content)
    issues = validate_invoice(data)
    report = format_report(data, issues)
    return data, issues, report


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Invoice Processor", page_icon="🧾", layout="wide")

st.title("🧾 Intelligent Invoice Processing System")
st.markdown("Upload an invoice (PDF, image, or text) to extract and validate structured financial data.")

uploaded_file = st.file_uploader(
    "Upload Invoice",
    type=["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "webp", "txt"],
    help="Supports PDF, images (PNG/JPG/etc.), and plain text files.",
)

if uploaded_file:
    st.info(f"Processing **{uploaded_file.name}** …")
    with st.spinner("Extracting and analysing invoice…"):
        try:
            file_bytes = uploaded_file.read()
            data, issues, report = process_invoice(file_bytes, uploaded_file.name)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Extracted Data (JSON)")
                st.json(data)

            with col2:
                st.subheader("Formatted Report")
                st.code(report, language="text")

            if issues:
                st.warning(f"**{len(issues)} validation issue(s) found:**")
                for issue in issues:
                    st.warning(f"• {issue}")
            else:
                st.success("All validation checks passed ✓")

            st.download_button(
                label="Download JSON",
                data=json.dumps(data, indent=2),
                file_name=f"{Path(uploaded_file.name).stem}_extracted.json",
                mime="application/json",
            )
            st.download_button(
                label="Download Report",
                data=report,
                file_name=f"{Path(uploaded_file.name).stem}_report.txt",
                mime="text/plain",
            )

        except Exception as e:
            st.error(f"**Error processing invoice:** {e}")
