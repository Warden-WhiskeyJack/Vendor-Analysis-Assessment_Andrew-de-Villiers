#!/usr/bin/env python3
"""
Merge Prefilled Vendor Data with Claude Batch Results.

Purpose:
    Combines rule-based prefilled vendor data with LLM-generated classifications.
    Performs validation, reconciles spend totals, and produces final output files
    ready for spreadsheet import.

Inputs:
    - 02_working/vendors_prefilled.csv: All vendors with prefill columns
    - 03_outputs/01_claude_batches/batch_*.csv: LLM classification results
    - 01_inputs/vendors_raw.csv: Original input for spend reconciliation

Outputs:
    - 03_outputs/vendors_final_for_sheet.csv: Final data with exact headers for import
    - 03_outputs/vendors_with_qc_columns.csv: All data including QC metadata
    - 03_outputs/process_metrics.md: Processing statistics and metrics

Algorithm:
    1. Load prefilled vendor data and build match keys
    2. Load Claude batch results, matching to prefilled via multiple strategies
    3. Merge data (prefill values take precedence over Claude values)
    4. Validate departments and suggestions against allowed lists
    5. Write output files and verify spend reconciliation

Matching Strategy:
    Vendor names may differ between prefilled and batch files due to encoding.
    We use multiple matching strategies (in order of preference):
    - Strategy 1: Normalized alphanumeric + spend amount
    - Strategy 2: Alternative normalization via clean_vendor_name
    - Strategy 3: Original unicode normalization
    - Strategy 4: Spend-only match if unique
    - Strategy 5: Fuzzy match on spend-matching candidates (65% threshold)

How to run:
    python 04_code/03_merge_results.py

    Requires vendors_prefilled.csv and batch_*.csv files to exist.
"""

import csv
import glob
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

# =============================================================================
# Constants and Validation Rules
# =============================================================================

# Allowed values for vendor classification
ALLOWED_DEPARTMENTS = [
    "Engineering",
    "Facilities",
    "G&A",
    "Legal",
    "M&A",
    "Marketing",
    "SaaS",
    "Product",
    "Professional Services",
    "Sales",
    "Support",
    "Finance",
]

ALLOWED_SUGGESTIONS = ["Consolidate", "Terminate", "Optimize costs"]

# Maximum words in description (truncated for spreadsheet display)
MAX_DESCRIPTION_WORDS = 15

# Fuzzy match threshold for vendor name matching (see Strategy 5 in docstring).
# 65% balances catching encoding variations vs avoiding false matches.
# Lower values risk incorrect matches; higher values miss legitimate variations.
FUZZY_MATCH_THRESHOLD = 0.65

# Paths (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent
PREFILLED_CSV = PROJECT_ROOT / "02_working" / "vendors_prefilled.csv"
CLAUDE_BATCHES_DIR = PROJECT_ROOT / "03_outputs" / "01_claude_batches"
VENDORS_RAW_CSV = PROJECT_ROOT / "01_inputs" / "vendors_raw.csv"
OUTPUT_DIR = PROJECT_ROOT / "03_outputs"


# =============================================================================
# Vendor Name Normalization Functions
# =============================================================================

def normalize_for_match(name: str, spend: float) -> str:
    """
    Create a normalized key for matching vendors between files.

    Uses spend amount + normalized name to handle encoding and case differences.
    The spend amount helps disambiguate vendors with similar names.

    Args:
        name: Vendor name to normalize.
        spend: Vendor spend amount (used as part of key).

    Returns:
        Match key in format "spend:normalized_name".
    """
    # Remove accents and special characters
    normalized = unicodedata.normalize("NFKD", name)
    # Keep only ASCII alphanumeric and spaces
    normalized = "".join(c for c in normalized if c.isascii() and (c.isalnum() or c.isspace()))
    # Lowercase and collapse whitespace
    normalized = " ".join(normalized.lower().split())
    # Combine with spend for unique key (spend as int to avoid float precision issues)
    return f"{int(spend)}:{normalized}"


def clean_vendor_name(name: str) -> str:
    """
    Clean vendor name using same logic as 01_normalize_vendors.py.

    Args:
        name: Raw vendor name.

    Returns:
        Cleaned name (lowercase, unicode normalized, no special chars).
    """
    # Lowercase
    cleaned = name.lower()
    # Normalize unicode
    cleaned = unicodedata.normalize("NFKD", cleaned)
    # Replace special chars with spaces
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    # Collapse whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned


def normalize_for_match_v2(name: str, spend: float) -> str:
    """
    Alternative normalization using simpler cleaning (Strategy 2).

    Args:
        name: Vendor name to normalize.
        spend: Vendor spend amount.

    Returns:
        Match key in format "spend:alphanumeric_only".
    """
    cleaned = clean_vendor_name(name)
    # Extract just alphanumeric chars for matching
    alpha_only = "".join(c for c in cleaned if c.isalnum())
    return f"{int(spend)}:{alpha_only}"


# =============================================================================
# Data Loading Functions
# =============================================================================

def load_prefilled_data() -> Tuple[Dict[str, dict], Dict[str, str]]:
    """
    Load vendors_prefilled.csv and build match key lookup.

    Returns:
        Tuple of (vendors dict keyed by vendor_name_raw, match_keys dict).
    """
    vendors = {}
    match_keys = {}  # normalized key -> vendor_name_raw

    with open(PREFILLED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor_name = row["vendor_name_raw"]
            spend = float(row["spend_usd"])

            # Use vendor_name_clean from the file (already normalized)
            vendor_clean = row.get("vendor_name_clean", "")

            # Create match key using the pre-cleaned name
            if vendor_clean:
                # Use alphanumeric only from cleaned name
                alpha_only = "".join(c for c in vendor_clean if c.isalnum())
                match_key = f"{int(spend)}:{alpha_only}"
            else:
                match_key = normalize_for_match(vendor_name, spend)

            # Also store alternative match key using v2 normalization
            alt_key = normalize_for_match_v2(vendor_name, spend)

            vendors[vendor_name] = {
                "vendor_name_raw": vendor_name,
                "spend_usd": spend,
                "vendor_name_clean": vendor_clean,
                "vendor_name_canonical": row.get("vendor_name_canonical", ""),
                "department_prefill": row.get("department_prefill", ""),
                "category_prefill": row.get("category_prefill", ""),
                "description_prefill": row.get("description_prefill", ""),
                "suggestion_prefill": row.get("suggestion_prefill", ""),
                "rule_id": row.get("rule_id", ""),
                "needs_llm": row.get("needs_llm", "True") == "True",
                "match_key": match_key,
            }
            match_keys[match_key] = vendor_name
            if alt_key != match_key:
                match_keys[alt_key] = vendor_name

    return vendors, match_keys


def load_claude_batches(match_keys: Dict[str, str]) -> Dict[str, dict]:
    """
    Load all batch_*.csv files from Claude output.

    Uses match_keys to resolve vendor names that differ due to encoding.
    Applies multiple matching strategies in order of preference to handle
    encoding variations between input and output files.

    Args:
        match_keys: Dictionary mapping normalized keys to vendor_name_raw.

    Returns:
        Dict keyed by canonical vendor_name_raw from prefilled data.
    """
    claude_data: Dict[str, dict] = {}
    batch_files = sorted(glob.glob(str(CLAUDE_BATCHES_DIR / "batch_*.csv")))
    unmatched: List[Tuple[str, float]] = []

    for batch_file in batch_files:
        with open(batch_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                vendor_name = row["vendor_name_raw"]
                spend = float(row["spend_usd"])

                # Try multiple matching strategies (in order of reliability)
                canonical_name = None

                # Strategy 1: Alphanumeric normalization (most common match)
                cleaned = clean_vendor_name(vendor_name)
                alpha_only = "".join(c for c in cleaned if c.isalnum())
                batch_key1 = f"{int(spend)}:{alpha_only}"
                if batch_key1 in match_keys:
                    canonical_name = match_keys[batch_key1]

                # Strategy 2: Alternative normalization via helper function
                if canonical_name is None:
                    batch_key2 = normalize_for_match_v2(vendor_name, spend)
                    if batch_key2 in match_keys:
                        canonical_name = match_keys[batch_key2]

                # Strategy 3: Unicode NFKD normalization (handles accents)
                if canonical_name is None:
                    batch_key3 = normalize_for_match(vendor_name, spend)
                    if batch_key3 in match_keys:
                        canonical_name = match_keys[batch_key3]

                # Strategy 4: Spend-only match (if only one vendor at that spend level)
                if canonical_name is None:
                    spend_matches = [k for k in match_keys.keys() if k.startswith(f"{int(spend)}:")]
                    if len(spend_matches) == 1:
                        canonical_name = match_keys[spend_matches[0]]

                # Strategy 5: Fuzzy match on spend-matching candidates
                # Uses simple character position matching with length penalty.
                # Threshold prevents false matches on short/common names.
                if canonical_name is None and spend_matches:
                    batch_alpha = "".join(c for c in cleaned if c.isalnum())
                    best_match = None
                    best_ratio = 0.0
                    for key in spend_matches:
                        _, prefilled_alpha = key.split(":", 1)
                        max_len = max(len(batch_alpha), len(prefilled_alpha))
                        min_len = min(len(batch_alpha), len(prefilled_alpha))
                        if max_len > 0:
                            # Count matching chars at each position
                            matches = sum(
                                1 for i in range(min_len) if batch_alpha[i] == prefilled_alpha[i]
                            )
                            # Apply penalty for length differences
                            length_penalty = abs(len(batch_alpha) - len(prefilled_alpha)) / max_len
                            ratio = (matches / max_len) - (length_penalty * 0.1)
                            if ratio > best_ratio and ratio > FUZZY_MATCH_THRESHOLD:
                                best_ratio = ratio
                                best_match = match_keys[key]
                    if best_match:
                        canonical_name = best_match

                if canonical_name is None:
                    unmatched.append((vendor_name, spend))
                    canonical_name = vendor_name

                claude_data[canonical_name] = {
                    "department_claude": row.get("department", ""),
                    "category_claude": row.get("category", ""),
                    "description_claude": row.get("description_1l", ""),
                    "suggestion_claude": row.get("suggestion", ""),
                    "confidence": row.get("confidence", ""),
                    "rationale_short": row.get("rationale_short", ""),
                    "suspected_duplicates": row.get("suspected_duplicates", ""),
                }

    if unmatched:
        print(f"      Warning: {len(unmatched)} vendors from batches not matched to prefilled:")
        for name, spend in unmatched[:5]:
            print(f"        - {name} (${spend:,.0f})")
        if len(unmatched) > 5:
            print(f"        ... and {len(unmatched) - 5} more")

    return claude_data


def load_raw_spend() -> Tuple[float, Dict[str, float]]:
    """
    Load vendors_raw.csv for spend reconciliation.

    Returns:
        Tuple of (total_spend, vendor_spend_dict).
    """
    total_spend = 0.0
    vendor_spend = {}

    with open(VENDORS_RAW_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle the exact header names with spaces
            vendor_name = row.get(" Vendor Name ", "").strip()
            cost_str = row.get("Last 12 months Cost (USD)", "")

            # Parse currency: "$3,117,226" -> 3117226.0
            cost = 0.0
            if cost_str:
                cost_clean = cost_str.replace("$", "").replace(",", "").strip()
                if cost_clean:
                    cost = float(cost_clean)

            total_spend += cost
            vendor_spend[vendor_name] = cost

    return total_spend, vendor_spend


# =============================================================================
# Validation and Transformation Functions
# =============================================================================

def truncate_description(desc: str, max_words: int = MAX_DESCRIPTION_WORDS) -> str:
    """
    Truncate description to max_words and ensure single line.

    Args:
        desc: Description text to truncate.
        max_words: Maximum number of words allowed.

    Returns:
        Truncated description (no trailing ellipsis).
    """
    if not desc:
        return ""

    # Remove newlines and extra whitespace
    desc = " ".join(desc.split())

    words = desc.split()
    if len(words) > max_words:
        words = words[:max_words]
        desc = " ".join(words)
        # Don't add ellipsis - just truncate

    return desc


def validate_department(dept: str) -> Tuple[bool, str]:
    """
    Validate department is in allowed list.

    Attempts case-insensitive matching for leniency.

    Args:
        dept: Department value to validate.

    Returns:
        Tuple of (is_valid, corrected_value).
    """
    if not dept:
        return False, ""

    dept = dept.strip()
    if dept in ALLOWED_DEPARTMENTS:
        return True, dept

    # Try case-insensitive match
    dept_lower = dept.lower()
    for allowed in ALLOWED_DEPARTMENTS:
        if allowed.lower() == dept_lower:
            return True, allowed

    return False, dept


def validate_suggestion(sugg: str) -> Tuple[bool, str]:
    """
    Validate suggestion is in allowed list.

    Attempts case-insensitive matching for leniency.

    Args:
        sugg: Suggestion value to validate.

    Returns:
        Tuple of (is_valid, corrected_value).
    """
    if not sugg:
        return False, ""

    sugg = sugg.strip()
    if sugg in ALLOWED_SUGGESTIONS:
        return True, sugg

    # Try case-insensitive match
    sugg_lower = sugg.lower()
    for allowed in ALLOWED_SUGGESTIONS:
        if allowed.lower() == sugg_lower:
            return True, allowed

    return False, sugg


# =============================================================================
# Data Merging and Output Functions
# =============================================================================

def merge_vendor_data(
    prefilled: Dict[str, dict], claude: Dict[str, dict]
) -> List[dict]:
    """
    Merge prefilled and Claude data, preferring prefill when present.

    Prefill values (from deterministic rules) take precedence over Claude values.
    This ensures consistency for known vendor patterns.

    Args:
        prefilled: Dict of prefilled vendor data.
        claude: Dict of Claude LLM results.

    Returns:
        List of merged vendor records with validation warnings logged.
    """
    merged = []
    validation_errors = []

    for vendor_name, pf in prefilled.items():
        cd = claude.get(vendor_name, {})

        # Determine final values: prefer prefill, fallback to Claude
        dept_pf = pf.get("department_prefill", "")
        dept_cl = cd.get("department_claude", "")
        department_final = dept_pf if dept_pf else dept_cl

        cat_pf = pf.get("category_prefill", "")
        cat_cl = cd.get("category_claude", "")
        category_final = cat_pf if cat_pf else cat_cl

        desc_pf = pf.get("description_prefill", "")
        desc_cl = cd.get("description_claude", "")
        description_raw = desc_pf if desc_pf else desc_cl
        description_final = truncate_description(description_raw)

        sugg_pf = pf.get("suggestion_prefill", "")
        sugg_cl = cd.get("suggestion_claude", "")
        suggestion_final = sugg_pf if sugg_pf else sugg_cl

        # Track source
        source = "prefill" if not pf.get("needs_llm", True) else "claude"

        # Validate department
        dept_valid, department_final = validate_department(department_final)
        if not dept_valid and department_final:
            validation_errors.append(
                f"  - {vendor_name}: invalid department '{department_final}'"
            )

        # Validate suggestion
        sugg_valid, suggestion_final = validate_suggestion(suggestion_final)
        if not sugg_valid and suggestion_final:
            validation_errors.append(
                f"  - {vendor_name}: invalid suggestion '{suggestion_final}'"
            )

        # Check for blanks
        if not department_final:
            validation_errors.append(f"  - {vendor_name}: blank department")
        if not description_final:
            validation_errors.append(f"  - {vendor_name}: blank description")
        if not suggestion_final:
            validation_errors.append(f"  - {vendor_name}: blank suggestion")

        merged.append(
            {
                "vendor_name_raw": vendor_name,
                "spend_usd": pf["spend_usd"],
                "department_final": department_final,
                "category_final": category_final,
                "description_final": description_final,
                "suggestion_final": suggestion_final,
                "confidence": cd.get("confidence", "N/A"),
                "rationale_short": cd.get("rationale_short", ""),
                "suspected_duplicates": cd.get("suspected_duplicates", ""),
                "rule_id": pf.get("rule_id", ""),
                "needs_llm": pf.get("needs_llm", True),
                "source": source,
            }
        )

    if validation_errors:
        print(f"Validation warnings ({len(validation_errors)}):")
        for err in validation_errors[:20]:  # Show first 20
            print(err)
        if len(validation_errors) > 20:
            print(f"  ... and {len(validation_errors) - 20} more")

    return merged


def write_final_for_sheet(merged: List[dict], output_path: Path) -> float:
    """
    Write the final CSV for spreadsheet import with exact headers.

    Args:
        merged: List of merged vendor records.
        output_path: Path to output CSV file.

    Returns:
        Total spend across all vendors (for reconciliation).
    """
    total_spend = 0.0

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Exact headers as specified
        writer.writerow(
            [
                "Vendor Name",
                "Department",
                "Last 12 months Cost (USD)",
                "1-line Description on what the Vendor does",
                "Suggestions (Consolidate / Terminate / Optimize costs)",
            ]
        )

        for row in merged:
            spend = row["spend_usd"]
            total_spend += spend
            writer.writerow(
                [
                    row["vendor_name_raw"],
                    row["department_final"],
                    f"${spend:,.0f}",
                    row["description_final"],
                    row["suggestion_final"],
                ]
            )

    return total_spend


def write_qc_columns(merged: List[dict], output_path: Path) -> None:
    """
    Write the QC version with all columns including metadata.

    Args:
        merged: List of merged vendor records.
        output_path: Path to output CSV file.
    """
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "vendor_name_raw",
            "spend_usd",
            "department_final",
            "category_final",
            "suggestion_final",
            "description_final",
            "confidence",
            "rationale_short",
            "suspected_duplicates",
            "rule_id",
            "needs_llm",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in merged:
            writer.writerow(
                {
                    "vendor_name_raw": row["vendor_name_raw"],
                    "spend_usd": row["spend_usd"],
                    "department_final": row["department_final"],
                    "category_final": row["category_final"],
                    "suggestion_final": row["suggestion_final"],
                    "description_final": row["description_final"],
                    "confidence": row["confidence"],
                    "rationale_short": row["rationale_short"],
                    "suspected_duplicates": row["suspected_duplicates"],
                    "rule_id": row["rule_id"],
                    "needs_llm": row["needs_llm"],
                }
            )


def write_process_metrics(merged: List[dict], output_path: Path) -> None:
    """
    Write process metrics markdown file.

    Generates statistics including prefill vs Claude counts, confidence
    distribution, and top vendors by spend.

    Args:
        merged: List of merged vendor records.
        output_path: Path to output markdown file.
    """
    total_count = len(merged)
    prefilled_count = sum(1 for r in merged if not r.get("needs_llm", True))
    claude_count = total_count - prefilled_count

    # Confidence distribution (only for Claude-processed)
    confidence_dist = {"High": 0, "Medium": 0, "Low": 0, "N/A": 0}
    for r in merged:
        conf = r.get("confidence", "N/A")
        if conf in confidence_dist:
            confidence_dist[conf] += 1
        else:
            confidence_dist["N/A"] += 1

    # Top 25 by spend - check low confidence
    sorted_by_spend = sorted(merged, key=lambda x: x["spend_usd"], reverse=True)
    top_25 = sorted_by_spend[:25]
    low_conf_in_top25 = sum(1 for r in top_25 if r.get("confidence") == "Low")

    # Total spend
    total_spend = sum(r["spend_usd"] for r in merged)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Vendor Processing Metrics\n\n")
        f.write(f"Generated by `03_merge_results.py`\n\n")
        f.write("## Summary Statistics\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Total Vendors | {total_count} |\n")
        f.write(f"| Total Spend | ${total_spend:,.2f} |\n")
        f.write(
            f"| Prefilled (rule-based) | {prefilled_count} ({100*prefilled_count/total_count:.1f}%) |\n"
        )
        f.write(
            f"| Claude-processed | {claude_count} ({100*claude_count/total_count:.1f}%) |\n"
        )
        f.write("\n")

        f.write("## Confidence Distribution\n\n")
        f.write("Confidence levels for Claude-processed vendors:\n\n")
        f.write("| Confidence | Count | Percentage |\n")
        f.write("|------------|-------|------------|\n")
        for level in ["High", "Medium", "Low", "N/A"]:
            count = confidence_dist[level]
            pct = 100 * count / total_count if total_count > 0 else 0
            f.write(f"| {level} | {count} | {pct:.1f}% |\n")
        f.write("\n")

        f.write("## Top 25 Vendors by Spend\n\n")
        f.write(
            f"Low-confidence count among top 25 by spend: **{low_conf_in_top25}**\n\n"
        )

        f.write("| Rank | Vendor | Spend | Confidence | Source |\n")
        f.write("|------|--------|-------|------------|--------|\n")
        for i, r in enumerate(top_25, 1):
            source = "Prefill" if not r.get("needs_llm", True) else "Claude"
            conf = r.get("confidence", "N/A")
            f.write(
                f"| {i} | {r['vendor_name_raw'][:40]} | ${r['spend_usd']:,.0f} | {conf} | {source} |\n"
            )
        f.write("\n")

        f.write("## Data Quality Notes\n\n")
        f.write(
            "- All departments validated against 12 allowed values\n"
        )
        f.write(
            "- All suggestions validated against: Consolidate, Terminate, Optimize costs\n"
        )
        f.write("- Descriptions truncated to 15 words maximum\n")
        f.write("- Spend reconciliation performed against raw input\n")


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """
    Main entry point for merge results.

    Returns:
        Exit code (0 for success, 1 for reconciliation failure).
    """
    print("=" * 60)
    print("MERGE VENDOR ANALYSIS RESULTS")
    print("=" * 60)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    print("\n[1/6] Loading prefilled vendor data...")
    prefilled, match_keys = load_prefilled_data()
    print(f"      Loaded {len(prefilled)} vendors from prefilled.csv")

    print("\n[2/6] Loading Claude batch results...")
    claude = load_claude_batches(match_keys)
    print(f"      Loaded {len(claude)} vendors from Claude batches")

    print("\n[3/6] Loading raw spend for reconciliation...")
    raw_total_spend, raw_vendor_spend = load_raw_spend()
    print(f"      Raw total spend: ${raw_total_spend:,.2f}")

    # Merge data
    print("\n[4/6] Merging vendor data (prefill preferred)...")
    merged = merge_vendor_data(prefilled, claude)
    print(f"      Merged {len(merged)} vendors")

    # Write outputs
    print("\n[5/6] Writing output files...")

    final_path = OUTPUT_DIR / "vendors_final_for_sheet.csv"
    final_spend = write_final_for_sheet(merged, final_path)
    print(f"      - {final_path.name}: {len(merged)} rows")

    qc_path = OUTPUT_DIR / "vendors_with_qc_columns.csv"
    write_qc_columns(merged, qc_path)
    print(f"      - {qc_path.name}: {len(merged)} rows")

    metrics_path = OUTPUT_DIR / "process_metrics.md"
    write_process_metrics(merged, metrics_path)
    print(f"      - {metrics_path.name}")

    # Spend reconciliation
    print("\n[6/6] Spend reconciliation...")
    spend_diff = abs(raw_total_spend - final_spend)
    print(f"      Raw input total:   ${raw_total_spend:,.2f}")
    print(f"      Final output total: ${final_spend:,.2f}")
    print(f"      Difference:         ${spend_diff:.2f}")

    # Spend reconciliation threshold: $0.01 allows for floating point rounding
    if spend_diff > 0.01:
        print("\nERROR: RECONCILIATION FAILED!")
        print(f"  Spend difference ${spend_diff:.2f} exceeds $0.01 threshold")
        return 1

    print("  Reconciliation passed (difference <= $0.01)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    prefilled_count = sum(1 for r in merged if not r.get("needs_llm", True))
    claude_count = len(merged) - prefilled_count
    print(f"Total vendors: {len(merged)}")
    print(f"Prefilled:     {prefilled_count} ({100*prefilled_count/len(merged):.1f}%)")
    print(f"Claude-filled: {claude_count} ({100*claude_count/len(merged):.1f}%)")
    print(f"Total spend:   ${final_spend:,.2f}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
