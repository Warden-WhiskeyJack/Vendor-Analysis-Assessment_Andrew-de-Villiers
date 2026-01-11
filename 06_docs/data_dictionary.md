# Data Dictionary

## Overview
This document defines all datasets produced during vendor analysis and their column specifications.

---

## Dataset: `vendors_normalized.csv`
**Location:** `02_working/`
**Description:** Raw vendor data with normalized names and spend figures.

| Column | Type | Description | Allowed Values |
|--------|------|-------------|----------------|
| `vendor_name_raw` | string | Original vendor name from source data | Any string |
| `spend_usd` | float | Annual vendor spend in USD | Positive numbers |
| `vendor_name_clean` | string | Lowercase, whitespace-trimmed vendor name | Any string |
| `vendor_name_canonical` | string | Canonical name for matching rules | Any string |

---

## Dataset: `vendors_prefilled.csv`
**Location:** `02_working/`
**Description:** All vendors with deterministic prefill rules applied.

| Column | Type | Description | Allowed Values |
|--------|------|-------------|----------------|
| `vendor_name_raw` | string | Original vendor name | Any string |
| `spend_usd` | float | Annual vendor spend in USD | Positive numbers |
| `vendor_name_clean` | string | Cleaned vendor name | Any string |
| `vendor_name_canonical` | string | Canonical name used for matching | Any string |
| `department_prefill` | string | Pre-filled department | See **Departments** below |
| `category_prefill` | string | Pre-filled category | See **Categories** below |
| `description_prefill` | string | Pre-filled vendor description | ≤ 15 words |
| `suggestion_prefill` | string | Pre-filled strategic recommendation | See **Suggestions** below |
| `rule_id` | string | ID of the matching prefill rule | Rule ID (e.g., R001) or empty |
| `needs_llm` | boolean | Whether vendor requires LLM processing | `True` or `False` |

---

## Dataset: `vendors_needing_llm.csv`
**Location:** `02_working/`
**Description:** Subset of vendors where prefill rules did not provide complete data.

**Columns:** Same as `vendors_prefilled.csv`, filtered where `needs_llm = True`.

---

## Dataset: `batch_XXX_input.csv`
**Location:** `02_working/01_batches/`
**Description:** Batch input files for Claude API processing (50 vendors per batch by default).

| Column | Type | Description | Allowed Values |
|--------|------|-------------|----------------|
| `vendor_name_raw` | string | Original vendor name | Any string |
| `spend_usd` | float | Annual vendor spend in USD | Positive numbers |

---

## Dataset: `batch_manifest.csv`
**Location:** `02_working/01_batches/`
**Description:** Manifest tracking all generated batch files.

| Column | Type | Description | Allowed Values |
|--------|------|-------------|----------------|
| `batch_id` | string | Unique batch identifier | `batch_001`, `batch_002`, etc. |
| `input_file` | string | Input batch filename | `batch_XXX_input.csv` |
| `row_start` | integer | Starting row number (inclusive) | Positive integer |
| `row_end` | integer | Ending row number (inclusive) | Positive integer |
| `vendor_count` | integer | Number of vendors in batch | Positive integer |
| `total_spend` | float | Total USD spend for batch | Positive number |

---

## Dataset: `batch_XXX_output.csv`
**Location:** `03_outputs/01_claude_batches/`
**Description:** Claude API output containing department, category, description, and recommendation.

| Column | Type | Description | Allowed Values |
|--------|------|-------------|----------------|
| `vendor_name_raw` | string | Original vendor name | Any string |
| `spend_usd` | float | Annual vendor spend in USD | Positive numbers |
| `department` | string | Assigned department | See **Departments** below |
| `category` | string | Vendor category | See **Categories** below |
| `description` | string | One-line vendor description | ≤ 15 words |
| `suggestion` | string | Strategic recommendation | See **Suggestions** below |
| `confidence` | string | Model confidence level | `High`, `Medium`, `Low` |
| `notes` | string | Additional notes or flags | Free text or empty |

---

## Controlled Value Lists

### Departments
Must be **exactly** one of the following 12 departments:

- `Engineering`
- `Facilities`
- `G&A`
- `Legal`
- `M&A`
- `Marketing`
- `SaaS`
- `Product`
- `Professional Services`
- `Sales`
- `Support`
- `Finance`

### Categories
Must be one of the following:

- `Cloud`
- `CRM`
- `Sales Engagement`
- `Travel & Expense`
- `Coworking/Office`
- `Telecom`
- `Recruiting`
- `Audit/Tax`
- `Legal Services`
- `Productivity/Collab`
- `Security/IT Ops`
- `Marketing/SEO/PR`
- `Product/Design`
- `Finance Systems`
- `General Ops`
- `Other`

### Suggestions
Must be **exactly** one of:

- `Consolidate`
- `Terminate`
- `Optimize costs`

---

## Validation Rules

1. **Department**: Must match the controlled list exactly (case-sensitive)
2. **Category**: Must match the controlled list exactly
3. **Suggestion**: Must match exactly one of the three allowed values
4. **Description**: Maximum 15 words
5. **Spend**: Must be positive number
6. **needs_llm**: Must be `True` if any of department/category/description/suggestion is missing
