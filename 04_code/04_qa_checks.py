#!/usr/bin/env python3
"""
04_qa_checks.py - QA validation and duplicate detection for vendor analysis.

Inputs:
- 03_outputs/vendors_with_qc_columns.csv
- 02_working/vendor_alias_map.csv

Outputs:
- 03_outputs/qa_report.md
- 03_outputs/possible_duplicates.csv

Prints QA PASS/FAIL with reasons.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Set

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
VENDORS_QC_CSV = PROJECT_ROOT / "03_outputs" / "vendors_with_qc_columns.csv"
ALIAS_MAP_CSV = PROJECT_ROOT / "02_working" / "vendor_alias_map.csv"
OUTPUT_DIR = PROJECT_ROOT / "03_outputs"

# Allowed values for validation
ALLOWED_DEPARTMENTS = [
    "Engineering", "Facilities", "G&A", "Legal", "M&A", "Marketing",
    "SaaS", "Product", "Professional Services", "Sales", "Support", "Finance",
]

ALLOWED_SUGGESTIONS = ["Consolidate", "Terminate", "Optimize costs"]

# Alias map score threshold
ALIAS_SCORE_THRESHOLD = 92


def load_vendors_qc() -> List[dict]:
    """Load vendors_with_qc_columns.csv and return list of vendor records."""
    vendors = []
    with open(VENDORS_QC_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendors.append({
                "vendor_name_raw": row.get("vendor_name_raw", ""),
                "spend_usd": float(row.get("spend_usd", 0)),
                "department_final": row.get("department_final", ""),
                "category_final": row.get("category_final", ""),
                "suggestion_final": row.get("suggestion_final", ""),
                "description_final": row.get("description_final", ""),
                "confidence": row.get("confidence", ""),
                "rationale_short": row.get("rationale_short", ""),
                "suspected_duplicates": row.get("suspected_duplicates", ""),
                "rule_id": row.get("rule_id", ""),
                "needs_llm": row.get("needs_llm", ""),
            })
    return vendors


def load_alias_map() -> List[dict]:
    """Load vendor_alias_map.csv and return entries with score >= threshold."""
    aliases = []
    try:
        with open(ALIAS_MAP_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                score_str = row.get("similarity_score", "0")
                try:
                    score = float(score_str) if score_str else 0
                except ValueError:
                    score = 0
                if score >= ALIAS_SCORE_THRESHOLD:
                    aliases.append({
                        "canonical_name": row.get("canonical_name", ""),
                        "alias_name": row.get("alias_name", ""),
                        "similarity_score": score,
                    })
    except FileNotFoundError:
        print(f"Warning: {ALIAS_MAP_CSV} not found, skipping alias duplicates")
    return aliases


def validate_vendors(vendors: List[dict]) -> List[str]:
    """Validate all vendors and return list of issues."""
    issues = []

    for v in vendors:
        vendor_name = v["vendor_name_raw"]

        # Check blank/missing department
        if not v["department_final"].strip():
            issues.append(f"Blank department: {vendor_name}")
        elif v["department_final"] not in ALLOWED_DEPARTMENTS:
            issues.append(f"Invalid department '{v['department_final']}': {vendor_name}")

        # Check blank/missing suggestion
        if not v["suggestion_final"].strip():
            issues.append(f"Blank suggestion: {vendor_name}")
        elif v["suggestion_final"] not in ALLOWED_SUGGESTIONS:
            issues.append(f"Invalid suggestion '{v['suggestion_final']}': {vendor_name}")

        # Check blank/missing description
        if not v["description_final"].strip():
            issues.append(f"Blank description: {vendor_name}")

        # Check blank/missing category
        if not v["category_final"].strip():
            issues.append(f"Blank category: {vendor_name}")

        # Check blank vendor name
        if not vendor_name.strip():
            issues.append("Blank vendor name found")

    return issues


def aggregate_by_field(vendors: List[dict], field: str) -> List[Tuple[str, int, float]]:
    """Aggregate vendors by a field, returning (field_value, count, total_spend) descending by spend."""
    agg = defaultdict(lambda: {"count": 0, "spend": 0.0})

    for v in vendors:
        key = v.get(field, "") or "(blank)"
        agg[key]["count"] += 1
        agg[key]["spend"] += v["spend_usd"]

    results = [(k, d["count"], d["spend"]) for k, d in agg.items()]
    results.sort(key=lambda x: x[2], reverse=True)
    return results


def build_duplicate_groups(vendors: List[dict], aliases: List[dict]) -> List[dict]:
    """Build possible duplicate groups from alias map and suspected_duplicates field."""
    # Build vendor spend lookup
    vendor_spend = {v["vendor_name_raw"]: v["spend_usd"] for v in vendors}

    duplicate_groups = []
    group_id = 1
    seen_pairs: Set[tuple] = set()

    # Source 1: Alias map (score >= 92)
    for alias in aliases:
        canonical = alias["canonical_name"]
        alias_name = alias["alias_name"]
        score = alias["similarity_score"]

        # Create normalized pair for deduplication
        pair = tuple(sorted([canonical.lower(), alias_name.lower()]))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        # Calculate combined spend
        spend1 = vendor_spend.get(canonical, 0)
        spend2 = vendor_spend.get(alias_name, 0)

        # Also try to find by case-insensitive match
        if spend1 == 0:
            for vn, sp in vendor_spend.items():
                if vn.lower() == canonical.lower():
                    spend1 = sp
                    break
        if spend2 == 0:
            for vn, sp in vendor_spend.items():
                if vn.lower() == alias_name.lower():
                    spend2 = sp
                    break

        combined_spend = spend1 + spend2

        duplicate_groups.append({
            "group_id": f"A{group_id:03d}",
            "vendor_names": f"{canonical} | {alias_name}",
            "combined_spend": combined_spend,
            "source": "alias_map",
            "notes": f"Similarity score: {score:.1f}%",
        })
        group_id += 1

    # Source 2: Suspected duplicates from LLM
    llm_group_id = 1
    processed_vendors = set()

    for v in vendors:
        vendor_name = v["vendor_name_raw"]
        suspected = v.get("suspected_duplicates", "")

        if not suspected or not suspected.strip():
            continue

        # Skip if this vendor was already processed as part of another group
        if vendor_name.lower() in processed_vendors:
            continue

        # Parse suspected duplicates (may be comma or semicolon separated)
        duplicates_raw = suspected.replace(";", ",").split(",")
        duplicates = [d.strip() for d in duplicates_raw if d.strip()]

        if not duplicates:
            continue

        # Build the group including this vendor
        all_in_group = [vendor_name] + duplicates

        # Calculate combined spend
        combined = 0.0
        for name in all_in_group:
            spend = vendor_spend.get(name, 0)
            if spend == 0:
                # Case-insensitive fallback
                for vn, sp in vendor_spend.items():
                    if vn.lower() == name.lower():
                        spend = sp
                        break
            combined += spend

        # Mark as processed
        for name in all_in_group:
            processed_vendors.add(name.lower())

        duplicate_groups.append({
            "group_id": f"L{llm_group_id:03d}",
            "vendor_names": " | ".join(all_in_group),
            "combined_spend": combined,
            "source": "llm_flagged",
            "notes": f"LLM identified {len(all_in_group)} potential duplicates",
        })
        llm_group_id += 1

    # Sort by combined spend descending
    duplicate_groups.sort(key=lambda x: x["combined_spend"], reverse=True)

    return duplicate_groups


def write_qa_report(
    vendors: List[dict],
    issues: List[str],
    dept_agg: List[Tuple[str, int, float]],
    sugg_agg: List[Tuple[str, int, float]],
    cat_agg: List[Tuple[str, int, float]],
    output_path: Path,
) -> None:
    """Write the QA report markdown file."""
    total_vendors = len(vendors)
    total_spend = sum(v["spend_usd"] for v in vendors)

    # Sort vendors by spend for top 25
    sorted_vendors = sorted(vendors, key=lambda x: x["spend_usd"], reverse=True)
    top_25 = sorted_vendors[:25]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# QA Report - Vendor Analysis\n\n")
        f.write("Generated by `04_qa_checks.py`\n\n")

        # Summary
        f.write("## Summary\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Total Vendors | {total_vendors:,} |\n")
        f.write(f"| Total Spend | ${total_spend:,.2f} |\n")
        f.write(f"| Validation Issues | {len(issues)} |\n")
        f.write("\n")

        # Spend by Department
        f.write("## Spend by Department\n\n")
        f.write("| Department | Count | Spend | % of Total |\n")
        f.write("|------------|-------|-------|------------|\n")
        for dept, count, spend in dept_agg:
            pct = (spend / total_spend * 100) if total_spend > 0 else 0
            f.write(f"| {dept} | {count} | ${spend:,.0f} | {pct:.1f}% |\n")
        f.write("\n")

        # Spend by Suggestion
        f.write("## Spend by Suggestion\n\n")
        f.write("| Suggestion | Count | Spend | % of Total |\n")
        f.write("|------------|-------|-------|------------|\n")
        for sugg, count, spend in sugg_agg:
            pct = (spend / total_spend * 100) if total_spend > 0 else 0
            f.write(f"| {sugg} | {count} | ${spend:,.0f} | {pct:.1f}% |\n")
        f.write("\n")

        # Spend by Category
        f.write("## Spend by Category\n\n")
        f.write("| Category | Count | Spend | % of Total |\n")
        f.write("|----------|-------|-------|------------|\n")
        for cat, count, spend in cat_agg:
            pct = (spend / total_spend * 100) if total_spend > 0 else 0
            f.write(f"| {cat} | {count} | ${spend:,.0f} | {pct:.1f}% |\n")
        f.write("\n")

        # Top 25 Vendors
        f.write("## Top 25 Vendors by Spend\n\n")
        f.write("| Rank | Vendor | Spend | Department | Category | Suggestion | Confidence |\n")
        f.write("|------|--------|-------|------------|----------|------------|------------|\n")
        for i, v in enumerate(top_25, 1):
            vendor_name = v["vendor_name_raw"][:40]
            f.write(
                f"| {i} | {vendor_name} | ${v['spend_usd']:,.0f} | "
                f"{v['department_final']} | {v['category_final']} | "
                f"{v['suggestion_final']} | {v['confidence']} |\n"
            )
        f.write("\n")

        # Invalid/Blank Fields
        f.write("## Validation Issues\n\n")
        if issues:
            f.write(f"Found **{len(issues)}** validation issues:\n\n")
            for issue in issues[:50]:  # Show first 50
                f.write(f"- {issue}\n")
            if len(issues) > 50:
                f.write(f"\n*...and {len(issues) - 50} more issues*\n")
        else:
            f.write("No validation issues found. All fields are valid.\n")
        f.write("\n")


def write_duplicates_csv(duplicates: List[dict], output_path: Path) -> None:
    """Write the possible duplicates CSV file."""
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["group_id", "vendor_names", "combined_spend", "source", "notes"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for dup in duplicates:
            writer.writerow(dup)


def main():
    """Main entry point."""
    print("=" * 60)
    print("04_qa_checks.py - QA Validation and Duplicate Detection")
    print("=" * 60)

    qa_pass = True
    fail_reasons = []

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    print("\n[1/5] Loading vendor data...")
    vendors = load_vendors_qc()
    print(f"      Loaded {len(vendors)} vendors")

    print("\n[2/5] Loading alias map...")
    aliases = load_alias_map()
    print(f"      Loaded {len(aliases)} alias pairs (score >= {ALIAS_SCORE_THRESHOLD})")

    # Validate
    print("\n[3/5] Validating vendor data...")
    issues = validate_vendors(vendors)
    print(f"      Found {len(issues)} validation issues")

    if issues:
        qa_pass = False
        fail_reasons.append(f"{len(issues)} validation issues found")
        print("      Issues preview:")
        for issue in issues[:5]:
            print(f"        - {issue}")
        if len(issues) > 5:
            print(f"        ... and {len(issues) - 5} more")

    # Aggregate statistics
    print("\n[4/5] Computing aggregations...")
    dept_agg = aggregate_by_field(vendors, "department_final")
    sugg_agg = aggregate_by_field(vendors, "suggestion_final")
    cat_agg = aggregate_by_field(vendors, "category_final")
    print(f"      - {len(dept_agg)} departments")
    print(f"      - {len(sugg_agg)} suggestions")
    print(f"      - {len(cat_agg)} categories")

    # Build duplicate groups
    print("\n[5/5] Building duplicate groups...")
    duplicates = build_duplicate_groups(vendors, aliases)
    alias_dups = sum(1 for d in duplicates if d["source"] == "alias_map")
    llm_dups = sum(1 for d in duplicates if d["source"] == "llm_flagged")
    print(f"      - {alias_dups} from alias map")
    print(f"      - {llm_dups} from LLM detection")
    print(f"      - {len(duplicates)} total duplicate groups")

    # Write outputs
    print("\n[6/6] Writing output files...")

    qa_report_path = OUTPUT_DIR / "qa_report.md"
    write_qa_report(vendors, issues, dept_agg, sugg_agg, cat_agg, qa_report_path)
    print(f"      - {qa_report_path.name}")

    duplicates_path = OUTPUT_DIR / "possible_duplicates.csv"
    write_duplicates_csv(duplicates, duplicates_path)
    print(f"      - {duplicates_path.name}")

    # Summary statistics for pass/fail
    total_spend = sum(v["spend_usd"] for v in vendors)

    # Check for critical issues
    blank_depts = sum(1 for v in vendors if not v["department_final"].strip())
    blank_suggs = sum(1 for v in vendors if not v["suggestion_final"].strip())
    blank_descs = sum(1 for v in vendors if not v["description_final"].strip())

    if blank_depts > 0:
        qa_pass = False
        fail_reasons.append(f"{blank_depts} vendors with blank department")
    if blank_suggs > 0:
        qa_pass = False
        fail_reasons.append(f"{blank_suggs} vendors with blank suggestion")
    if blank_descs > 0:
        qa_pass = False
        fail_reasons.append(f"{blank_descs} vendors with blank description")

    # Print final result
    print("\n" + "=" * 60)
    if qa_pass:
        print("QA PASS")
        print("=" * 60)
        print("\nAll validations passed:")
        print(f"  - {len(vendors)} vendors processed")
        print(f"  - ${total_spend:,.2f} total spend")
        print(f"  - {len(duplicates)} possible duplicate groups identified")
        print(f"  - 0 validation issues")
    else:
        print("QA FAIL")
        print("=" * 60)
        print("\nFailure reasons:")
        for reason in fail_reasons:
            print(f"  - {reason}")

    print(f"\nOutputs created:")
    print(f"  - {qa_report_path}")
    print(f"  - {duplicates_path}")

    return 0 if qa_pass else 1


if __name__ == "__main__":
    sys.exit(main())
