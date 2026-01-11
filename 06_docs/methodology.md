# Methodology

## Overview

I conducted a vendor spend diligence assessment covering 386 vendors totaling $7,887,359 in annual spend. This document describes the end-to-end process I followed to categorize, describe, and recommend actions for each vendor.

## Input Capture

I started with `vendors_raw.csv` containing vendor names and 12-month spend figures. I referenced the assessment instructions in `00_admin/00_assessment_instructions.md` and the department rubric in `00_admin/01_department_rubric.md`, which defined 12 allowable departments and tie-break logic (function over delivery model).

## Normalization and Alias Mapping

I ran `01_normalize_vendors.py` to clean vendor names—lowercasing, collapsing whitespace, and stripping legal suffixes (LLC, Inc, GmbH, D.O.O., etc.). The script produced canonical names and identified potential duplicates via fuzzy matching (92% threshold). Outputs: `vendors_normalized.csv` and `vendor_alias_map.csv`.

## Deterministic Prefill and Category Tagging

I defined 34 rules in `prefill_rules.yml` covering well-known vendors (Salesforce, AWS, Microsoft, WeWork, etc.). Each rule specifies pattern, department, category, description template, and suggestion. Running `02_apply_prefill_rules.py` prefilled 77 vendors (19.9%); 309 vendors (80.1%) were flagged for LLM processing.

## Claude Batch Processing and Batch Log

I split the 309 remaining vendors into seven batches of up to 50 vendors each using `02b_make_batches.py`. For each batch, I submitted the vendor list to Claude with instructions to return: department, category, one-line description (≤15 words), suggestion (Consolidate/Terminate/Optimize costs), confidence level, rationale, and suspected duplicates. I documented each batch's confidence distribution, duplicate findings, and classification notes in `batch_log.md`. Across all batches, 153 vendors received high confidence, 100 medium, and 56 low.

## Spend Reconciliation and QA

I ran `03_merge_results.py` to combine prefilled and Claude-processed results into `vendors_final_for_sheet.csv` and `vendors_with_qc_columns.csv`. The script performed spend reconciliation—input and output totals matched exactly at $7,887,359.

I then ran `04_qa_checks.py` to validate all fields: no blanks, departments within 12 allowed values, suggestions within 3 allowed values, descriptions within word limits. The QA pass rate was 100%. The script also consolidated duplicate groups from both the alias map and Claude's suspected duplicates, outputting 51+ groups totaling approximately $1.5M in `possible_duplicates.csv`.

## Top 3 Opportunity Selection

Using the QA outputs, I identified the three highest-impact opportunities: Salesforce contract renegotiation ($3.1M, 39.5% of spend), duplicate vendor consolidation (51+ groups, ~$1.5M flagged), and termination of low-value/unclear vendors (57 vendors, $109K). Selection criteria prioritized spend magnitude, actionability, and implementation feasibility.

## Limitations and Assumptions

**Limitations**: Prefill rules cover only well-known vendors; 80% required LLM processing. Claude classified vendors based on name and spend only—no contracts or usage data. Duplicate detection within batches may miss cross-batch matches. Low-confidence classifications (14.5%) require manual validation.

**Assumptions**: I assumed vendor names are accurate, historical spend is representative, and fuzzy matching at 92% threshold captures meaningful duplicates without excessive false positives. Stakeholder review is expected before implementing recommendations.
