Write 04_code/03_merge_results.py (Python) that:

Inputs:
- 02_working/vendors_prefilled.csv
- all 03_outputs/01_claude_batches/batch_*.csv
- 01_inputs/vendors_raw.csv (for spend reconciliation)

Outputs:
1) 03_outputs/vendors_final_for_sheet.csv with EXACT headers:
Vendor Name
Department
Last 12 months Cost (USD)
1-line Description on what the Vendor does
Suggestions (Consolidate / Terminate / Optimize costs)

2) 03_outputs/vendors_with_qc_columns.csv including:
department_final, category_final, suggestion_final, description_final,
confidence, rationale_short, suspected_duplicates, rule_id, needs_llm, spend_usd, vendor_name_raw

Rules:
- Prefer prefill fields when present; otherwise use Claude fields.
- Validate: no blanks, department ∈ allowed 12, suggestion ∈ {Consolidate, Terminate, Optimize costs}
- Description must be one line and <= 15 words

Spend reconciliation:
- total spend in 01_inputs/vendors_raw.csv must equal total spend in vendors_final_for_sheet.csv within $0.01; else fail.

Process metrics:
- Write 03_outputs/process_metrics.md with:
  - total vendor count
  - count/% prefilled vs Claude-filled
  - confidence distribution
  - low-confidence count among top 25 by spend

Run the script and ensure outputs are created successfully.
