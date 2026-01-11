# Vendor Spend Diligence Assessment

Assessment of 386 vendors totaling $7,887,359 in annual spend. This pipeline normalizes vendor names, applies deterministic prefill rules, processes remaining vendors through Claude, and runs QA validation.

## Quickstart

```bash
# Run the full pipeline
make all

# Or run individual steps
make normalize   # Step 1: Normalize vendor names
make prefill     # Step 2: Apply prefill rules
make batches     # Step 3: Generate batch input files
make merge       # Step 4: Merge results
make qa          # Step 5: Run QA checks

# View available commands
make help

# Clean generated files
make clean
```

## Repository Structure

```
.
├── 00_admin/                   # Assessment instructions and department rubric
│   └── 02_links.md             # Paste Google Sheet and Memo links here
├── 01_inputs/
│   └── vendors_raw.csv         # Raw vendor data (name + spend)
├── 02_working/
│   ├── 01_batches/             # Batch input files for Claude
│   │   ├── batch_001_input.csv
│   │   └── batch_manifest.csv
│   ├── prefill_rules.yml       # 34 deterministic rules
│   ├── vendor_alias_map.csv    # Fuzzy-matched duplicates
│   ├── vendors_normalized.csv  # Normalized vendor names
│   ├── vendors_needing_llm.csv # Vendors requiring Claude
│   └── vendors_prefilled.csv   # Prefilled + flagged vendors
├── 03_outputs/
│   ├── 01_claude_batches/      # Claude batch outputs (batch_001.csv - batch_007.csv)
│   ├── vendors_final_for_sheet.csv
│   ├── vendors_with_qc_columns.csv
│   ├── qa_report.md
│   ├── possible_duplicates.csv
│   ├── process_metrics.md
│   └── top3_for_sheet.md
├── 04_code/                    # Pipeline scripts
├── 05_prompts/                 # Prompt templates for each step
├── 06_docs/
│   ├── batch_log.md            # Per-batch metadata and notes
│   ├── change_log.md           # Manual corrections log
│   ├── methodology.md          # Full methodology write-up
│   └── executive_memo.md       # Final memo
└── Makefile
```

## Reproduce Steps

1. **Normalize** (`01_normalize_vendors.py`): Clean vendor names (lowercase, strip legal suffixes), fuzzy-match potential duplicates at 92% threshold. Outputs `vendors_normalized.csv` and `vendor_alias_map.csv`.

2. **Prefill** (`02_apply_prefill_rules.py`): Apply 34 rules from `prefill_rules.yml` to tag known vendors (Salesforce, AWS, Microsoft, etc.) with department, category, description, and suggestion. Outputs `vendors_prefilled.csv` and `vendors_needing_llm.csv`.

3. **Make Batches** (`02b_make_batches.py`): Split vendors needing LLM into batches of 50. Outputs batch input files to `02_working/01_batches/`.

4. **Process with Claude**: Submit each batch to Claude with the classification prompt. Save outputs to `03_outputs/01_claude_batches/`. Document results in `06_docs/batch_log.md`.

5. **Merge** (`03_merge_results.py`): Combine prefilled and Claude-processed results. Verify spend reconciliation. Outputs `vendors_final_for_sheet.csv`, `vendors_with_qc_columns.csv`, and `process_metrics.md`.

6. **QA** (`04_qa_checks.py`): Validate all fields (no blanks, valid departments/suggestions, word limits). Consolidate duplicate groups. Outputs `qa_report.md`, `possible_duplicates.csv`, and `top3_for_sheet.md`.

## Claude Batch Locations

| Type | Location |
|------|----------|
| Batch inputs | `02_working/01_batches/batch_*_input.csv` |
| Batch manifest | `02_working/01_batches/batch_manifest.csv` |
| Batch outputs | `03_outputs/01_claude_batches/batch_*.csv` |

## Artifacts to Review

| Artifact | Location | Purpose |
|----------|----------|---------|
| `qa_report.md` | `03_outputs/` | Validation results, spend by department/category/suggestion, top 25 vendors |
| `possible_duplicates.csv` | `03_outputs/` | 51+ duplicate groups totaling ~$1.5M |
| `process_metrics.md` | `03_outputs/` | Summary stats: 386 vendors, 77 prefilled, 309 Claude-processed |
| `batch_log.md` | `06_docs/` | Per-batch confidence distribution, duplicate findings, classification notes |
| `change_log.md` | `06_docs/` | Manual corrections made after QA review |
| `top3_for_sheet.md` | `03_outputs/` | Top 3 opportunities: Salesforce ($3.1M), duplicates (~$1.5M), terminations ($109K) |

## Design Choices

### Normalization
- Lowercase, collapse whitespace, strip legal suffixes (LLC, Inc, GmbH, D.O.O., etc.)
- Fuzzy matching at 92% threshold to catch typos without excessive false positives
- Alias map preserves original names for audit trail

### Deterministic Prefill
- 34 rules in `prefill_rules.yml` covering well-known vendors
- Pattern types: `contains` and `regex`
- Each rule specifies department, category, description template, and suggestion
- Prefilled 77 vendors (19.9%), reducing LLM cost and ensuring consistency for known vendors

### Strict Schema
- 12 allowed departments (from `00_admin/01_department_rubric.md`)
- 16 allowed categories (from `prefill_rules.yml`)
- 3 allowed suggestions: Consolidate, Terminate, Optimize costs
- Descriptions capped at 15 words

### Spend Reconciliation
- Input total: $7,887,359
- Output total: $7,887,359
- Verified by `03_merge_results.py` before proceeding

### QA Validation
- No blank fields allowed
- All departments validated against allowed list
- All suggestions validated against allowed list
- Word limits enforced on descriptions
- Duplicate groups consolidated from alias map + Claude suspected duplicates
- 100% QA pass rate

## Deliverables

After completing the assessment, paste your final links into `00_admin/02_links.md`:

- **Google Sheet**: Final vendor analysis with all classifications
- **Executive Memo**: Summary findings and top 3 opportunities

---

**Project Status**: Complete
**Last Updated**: 2026-01-11
