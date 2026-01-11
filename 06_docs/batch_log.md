# Batch Processing Log

## Purpose
Record metadata and outcomes for each Claude API batch processed.

---

## Log Format

Each batch should be appended to the table below after processing completes.

| Batch ID | Input File | Output File | Row Range | Vendor Count | Total Spend | High Conf | Med Conf | Low Conf | Duplicates | Status | Notes |
|----------|------------|-------------|-----------|--------------|-------------|-----------|----------|----------|------------|--------|-------|
| batch_001 | batch_001_input.csv | batch_001_output.csv | 1-50 | 50 | $1,833,768 | 45 | 4 | 1 | 0 | ✅ Complete | No issues |
| batch_002 | batch_002_input.csv | batch_002_output.csv | 51-100 | 50 | $226,139 | 48 | 2 | 0 | 0 | ✅ Complete | |

---

## Column Definitions

- **Batch ID**: Unique identifier (e.g., `batch_001`)
- **Input File**: Name of input CSV in `02_working/01_batches/`
- **Output File**: Name of output CSV in `03_outputs/01_claude_batches/`
- **Row Range**: Vendor row numbers processed (e.g., `1-50`)
- **Vendor Count**: Number of vendors in batch
- **Total Spend**: Sum of `spend_usd` for all vendors in batch
- **High/Med/Low Conf**: Count of vendors by confidence level
- **Duplicates**: Number of duplicate vendor names flagged
- **Status**: Processing status (✅ Complete, ⚠️ Warning, ❌ Failed)
- **Notes**: Any issues, errors, or observations

---

## Instructions

1. Append a new row after each batch completes
2. Calculate confidence counts from output file
3. Flag duplicates if multiple vendors have identical canonical names
4. Use Status symbols for quick visual scanning
5. Record errors or anomalies in Notes field

---

## Batch Log Entries

| Batch ID | Input File | Output File | Row Range | Vendor Count | Total Spend | High Conf | Med Conf | Low Conf | Duplicates | Status | Notes |
|----------|------------|-------------|-----------|--------------|-------------|-----------|----------|----------|------------|--------|-------|
| | | | | | | | | | | | |
