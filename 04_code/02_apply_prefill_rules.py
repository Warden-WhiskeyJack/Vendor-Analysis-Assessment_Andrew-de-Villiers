#!/usr/bin/env python3
"""
Apply Prefill Rules to Normalized Vendors.

Purpose:
    Applies deterministic rule-based classification to normalized vendor data.
    Vendors matching known patterns are pre-filled with department, category,
    description, and suggestion values, reducing the need for LLM processing.

Inputs:
    - 02_working/vendors_normalized.csv: Normalized vendor data from step 01
    - 02_working/prefill_rules.yml: YAML file containing matching rules with:
        * categories: allowed category values
        * departments: allowed department values
        * rules: list of pattern-based classification rules

Outputs:
    - 02_working/vendors_prefilled.csv: All vendors with prefill columns added:
        * department_prefill, category_prefill, description_prefill, suggestion_prefill
        * rule_id (which rule matched), needs_llm (True/False)
    - 02_working/vendors_needing_llm.csv: Subset of vendors requiring LLM classification

Algorithm:
    1. Load and validate all rules from YAML
    2. For each vendor, try to match against rules (first match wins)
    3. Mark vendors with no rule match as needs_llm=True
    4. Output all vendors and the subset needing LLM processing

How to run:
    python 04_code/02_apply_prefill_rules.py

    Ensure input files exist in 02_working/ directory.
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# =============================================================================
# Constants and Validation Rules
# =============================================================================

# Allowed values for vendor classification (must match rules file)
ALLOWED_DEPARTMENTS = [
    'Engineering', 'Facilities', 'G&A', 'Legal', 'M&A', 'Marketing',
    'SaaS', 'Product', 'Professional Services', 'Sales', 'Support', 'Finance'
]

ALLOWED_SUGGESTIONS = ['Consolidate', 'Terminate', 'Optimize costs']

# Maximum words allowed in description (keeps output concise for spreadsheet)
MAX_DESCRIPTION_WORDS = 15


class PrefillRulesEngine:
    """
    Engine to apply prefill rules to vendor data.

    Loads rules from a YAML file and applies them to vendor names using
    either substring matching ('contains') or regex patterns ('regex').
    First matching rule wins.
    """

    def __init__(self, rules_file: Path) -> None:
        """
        Initialize the rules engine with rules from YAML file.

        Args:
            rules_file: Path to the prefill_rules.yml configuration file.
        """
        self.rules: List[Dict] = []
        self.categories: List[str] = []
        self.departments: List[str] = []
        self._load_rules(rules_file)

    def _load_rules(self, rules_file: Path) -> None:
        """Load rules from YAML file."""
        with open(rules_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.categories = data.get('categories', [])
        self.departments = data.get('departments', [])
        self.rules = data.get('rules', [])

        print(f"Loaded {len(self.rules)} rules from {rules_file.name}")
        print(f"  Categories defined: {len(self.categories)}")
        print(f"  Departments defined: {len(self.departments)}")

    def _validate_rule(self, rule: Dict) -> List[str]:
        """
        Validate a single rule against schema requirements.

        Args:
            rule: Dictionary containing rule definition.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []

        # Check required fields
        required_fields = ['id', 'match_type', 'pattern', 'department',
                          'category', 'description_template', 'suggestion', 'notes']
        for field in required_fields:
            if field not in rule:
                errors.append(f"Rule {rule.get('id', 'UNKNOWN')}: Missing field '{field}'")

        if errors:
            return errors

        # Validate department against module-level allowed list
        if rule['department'] not in ALLOWED_DEPARTMENTS:
            errors.append(
                f"Rule {rule['id']}: Invalid department '{rule['department']}'. "
                f"Must be one of: {', '.join(ALLOWED_DEPARTMENTS)}"
            )

        # Validate category against YAML-defined list
        if rule['category'] not in self.categories:
            errors.append(
                f"Rule {rule['id']}: Invalid category '{rule['category']}'. "
                f"Must be one of: {', '.join(self.categories)}"
            )

        # Validate suggestion against module-level allowed list
        if rule['suggestion'] not in ALLOWED_SUGGESTIONS:
            errors.append(
                f"Rule {rule['id']}: Invalid suggestion '{rule['suggestion']}'. "
                f"Must be exactly one of: {', '.join(ALLOWED_SUGGESTIONS)}"
            )

        # Validate description length against max word limit
        word_count = len(rule['description_template'].split())
        if word_count > MAX_DESCRIPTION_WORDS:
            errors.append(
                f"Rule {rule['id']}: Description has {word_count} words, "
                f"must be <= {MAX_DESCRIPTION_WORDS} words"
            )

        # Validate match_type
        if rule['match_type'] not in ['contains', 'regex']:
            errors.append(
                f"Rule {rule['id']}: Invalid match_type '{rule['match_type']}'. "
                f"Must be 'contains' or 'regex'"
            )

        return errors

    def validate_all_rules(self) -> bool:
        """Validate all rules. Returns True if all valid, False otherwise."""
        all_errors = []

        for rule in self.rules:
            errors = self._validate_rule(rule)
            all_errors.extend(errors)

        if all_errors:
            print("\n❌ Rule Validation Errors:")
            for error in all_errors:
                print(f"  - {error}")
            return False

        print("✅ All rules validated successfully")
        return True

    def _match_rule(self, vendor_name: str, rule: Dict) -> bool:
        """
        Check if a vendor name matches a rule pattern.

        Args:
            vendor_name: The vendor name to test.
            rule: Rule dictionary containing 'pattern' and 'match_type'.

        Returns:
            True if vendor matches the rule pattern, False otherwise.
        """
        pattern = rule['pattern']
        match_type = rule['match_type']

        # All matching is case-insensitive
        vendor_name_lower = vendor_name.lower()

        if match_type == 'contains':
            # Simple substring matching
            return pattern.lower() in vendor_name_lower
        elif match_type == 'regex':
            # Full regex pattern matching
            return bool(re.search(pattern, vendor_name_lower, re.IGNORECASE))

        return False

    def apply_rules(self, vendor_name: str) -> Tuple[Optional[str], Optional[str],
                                                     Optional[str], Optional[str],
                                                     Optional[str]]:
        """
        Apply rules to a vendor name (first match wins).

        Args:
            vendor_name: The vendor name to classify.

        Returns:
            Tuple of (department, category, description, suggestion, rule_id).
            All values are None if no rule matches.
        """
        for rule in self.rules:
            if self._match_rule(vendor_name, rule):
                return (
                    rule['department'],
                    rule['category'],
                    rule['description_template'],
                    rule['suggestion'],
                    rule['id']
                )

        return None, None, None, None, None


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """
    Main function to apply prefill rules to vendors.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Setup paths
    base_dir = Path(__file__).parent.parent
    working_dir = base_dir / '02_working'

    input_file = working_dir / 'vendors_normalized.csv'
    rules_file = working_dir / 'prefill_rules.yml'
    output_file = working_dir / 'vendors_prefilled.csv'
    llm_needed_file = working_dir / 'vendors_needing_llm.csv'

    # Validate input files exist
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        print("  Run 01_normalize_vendors.py first to generate this file.")
        return 1

    if not rules_file.exists():
        print(f"ERROR: Rules file not found: {rules_file}")
        print("  Ensure prefill_rules.yml exists in 02_working/ directory.")
        return 1

    # Load rules and validate
    print("\n" + "=" * 70)
    print("PREFILL RULES APPLICATION")
    print("=" * 70)

    engine = PrefillRulesEngine(rules_file)

    if not engine.validate_all_rules():
        print("\nERROR: Rule validation failed. Fix errors in prefill_rules.yml.")
        return 1

    # Read input vendors
    print(f"\nReading vendors from: {input_file.name}")
    vendors: List[Dict] = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        vendors = list(reader)

    print(f"  Found {len(vendors)} vendors to process")

    # Apply rules to each vendor
    print("\nApplying rules...")
    matched_count = 0
    needs_llm_count = 0

    output_rows: List[Dict] = []
    llm_needed_rows: List[Dict] = []

    for vendor in vendors:
        # Prefer canonical name (most normalized), fall back to cleaned name
        vendor_name = vendor.get('vendor_name_canonical', '') or vendor.get('vendor_name_clean', '')

        # Apply rules (first match wins)
        dept, cat, desc, sugg, rule_id = engine.apply_rules(vendor_name)

        # Build output row with original columns plus prefill results
        output_row = vendor.copy()
        output_row['department_prefill'] = dept or ''
        output_row['category_prefill'] = cat or ''
        output_row['description_prefill'] = desc or ''
        output_row['suggestion_prefill'] = sugg or ''
        output_row['rule_id'] = rule_id or ''

        # Vendor needs LLM if any required field is missing
        needs_llm = not all([dept, cat, desc, sugg])
        output_row['needs_llm'] = 'True' if needs_llm else 'False'

        output_rows.append(output_row)

        if rule_id:
            matched_count += 1

        if needs_llm:
            needs_llm_count += 1
            llm_needed_rows.append(output_row)

    # Determine output columns from first row
    output_columns = list(output_rows[0].keys()) if output_rows else []

    # Write all vendors to prefilled file
    print(f"\nWriting outputs...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"  {output_file.name}: {len(output_rows)} vendors")

    # Write vendors needing LLM to separate file
    with open(llm_needed_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(llm_needed_rows)
    print(f"  {llm_needed_file.name}: {len(llm_needed_rows)} vendors")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    pct_matched = (matched_count / len(vendors) * 100) if vendors else 0
    pct_llm = (needs_llm_count / len(vendors) * 100) if vendors else 0
    print(f"Total vendors processed:  {len(vendors)}")
    print(f"Matched by rules:         {matched_count} ({pct_matched:.1f}%)")
    print(f"Needing LLM processing:   {needs_llm_count} ({pct_llm:.1f}%)")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
