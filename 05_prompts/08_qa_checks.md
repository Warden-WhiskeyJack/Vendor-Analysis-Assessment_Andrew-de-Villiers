Write 04_code/04_qa_checks.py that reads 03_outputs/vendors_with_qc_columns.csv and produces:

1) 03_outputs/qa_report.md including:
- total vendors and total spend
- spend + count by Department (descending)
- spend + count by Suggestions (descending)
- spend + count by category (descending)
- top 25 vendors by spend (vendor, spend, dept, category, suggestion, confidence)
- list of any invalid/blank fields (should be none)

2) 03_outputs/possible_duplicates.csv combining:
- 02_working/vendor_alias_map.csv (score>=92)
- suspected_duplicates flagged in vendors_with_qc_columns
Include: group_id, vendor_names, combined_spend, source, notes

Print QA PASS/FAIL and why.

Run it and ensure outputs are created.
