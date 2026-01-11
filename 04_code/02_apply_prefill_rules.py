#!/usr/bin/env python3
"""
Apply prefill rules to normalized vendors.

Reads vendors_normalized.csv, applies deterministic rules from prefill_rules.yml,
and outputs vendors_prefilled.csv and vendors_needing_llm.csv.
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class PrefillRulesEngine:
    """Engine to apply prefill rules to vendor data."""

    ALLOWED_DEPARTMENTS = [
        'Engineering', 'Sales', 'Marketing', 'Finance', 'HR', 'Operations',
        'Product', 'Legal', 'Customer Success', 'IT', 'Executive', 'Facilities'
    ]

    ALLOWED_SUGGESTIONS = ['Consolidate', 'Terminate', 'Optimize costs']

    def __init__(self, rules_file: Path):
        """Initialize the rules engine with rules from YAML file."""
        self.rules = []
        self.categories = []
        self.departments = []
        self._load_rules(rules_file)

    def _load_rules(self, rules_file: Path) -> None:
        """Load rules from YAML file."""
        with open(rules_file, 'r') as f:
            data = yaml.safe_load(f)

        self.categories = data.get('categories', [])
        self.departments = data.get('departments', [])
        self.rules = data.get('rules', [])

        print(f"Loaded {len(self.rules)} rules from {rules_file}")
        print(f"Controlled categories: {len(self.categories)}")
        print(f"Allowed departments: {len(self.departments)}")

    def _validate_rule(self, rule: Dict) -> List[str]:
        """Validate a single rule. Returns list of validation errors."""
        errors = []

        # Check required fields
        required_fields = ['id', 'match_type', 'pattern', 'department',
                          'category', 'description_template', 'suggestion', 'notes']
        for field in required_fields:
            if field not in rule:
                errors.append(f"Rule {rule.get('id', 'UNKNOWN')}: Missing field '{field}'")

        if errors:
            return errors

        # Validate department
        if rule['department'] not in self.ALLOWED_DEPARTMENTS:
            errors.append(
                f"Rule {rule['id']}: Invalid department '{rule['department']}'. "
                f"Must be one of: {', '.join(self.ALLOWED_DEPARTMENTS)}"
            )

        # Validate category
        if rule['category'] not in self.categories:
            errors.append(
                f"Rule {rule['id']}: Invalid category '{rule['category']}'. "
                f"Must be one of: {', '.join(self.categories)}"
            )

        # Validate suggestion
        if rule['suggestion'] not in self.ALLOWED_SUGGESTIONS:
            errors.append(
                f"Rule {rule['id']}: Invalid suggestion '{rule['suggestion']}'. "
                f"Must be exactly one of: {', '.join(self.ALLOWED_SUGGESTIONS)}"
            )

        # Validate description length
        word_count = len(rule['description_template'].split())
        if word_count > 15:
            errors.append(
                f"Rule {rule['id']}: Description has {word_count} words, "
                f"must be <= 15 words"
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
        """Check if a vendor name matches a rule."""
        pattern = rule['pattern']
        match_type = rule['match_type']

        # Case-insensitive matching
        vendor_name_lower = vendor_name.lower()

        if match_type == 'contains':
            return pattern.lower() in vendor_name_lower
        elif match_type == 'regex':
            return bool(re.search(pattern, vendor_name_lower, re.IGNORECASE))

        return False

    def apply_rules(self, vendor_name: str) -> Tuple[Optional[str], Optional[str],
                                                       Optional[str], Optional[str],
                                                       Optional[str]]:
        """
        Apply rules to a vendor name.

        Returns: (department, category, description, suggestion, rule_id)
        Returns (None, None, None, None, None) if no rule matches.
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


def apply_prefill_rules():
    """Main function to apply prefill rules to vendors."""
    # Setup paths
    base_dir = Path(__file__).parent.parent
    working_dir = base_dir / '02_working'

    input_file = working_dir / 'vendors_normalized.csv'
    rules_file = working_dir / 'prefill_rules.yml'
    output_file = working_dir / 'vendors_prefilled.csv'
    llm_needed_file = working_dir / 'vendors_needing_llm.csv'

    # Check input files exist
    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        sys.exit(1)

    if not rules_file.exists():
        print(f"❌ Error: Rules file not found: {rules_file}")
        sys.exit(1)

    # Load rules and validate
    print("\n" + "=" * 70)
    print("PREFILL RULES APPLICATION")
    print("=" * 70)

    engine = PrefillRulesEngine(rules_file)

    if not engine.validate_all_rules():
        print("\n❌ Validation failed. Please fix the rules and try again.")
        sys.exit(1)

    # Read input vendors
    print(f"\nReading vendors from: {input_file}")
    vendors = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        vendors = list(reader)

    print(f"Found {len(vendors)} vendors to process")

    # Apply rules to each vendor
    print("\nApplying rules...")
    matched_count = 0
    needs_llm_count = 0

    output_rows = []
    llm_needed_rows = []

    for vendor in vendors:
        # Get the canonical name for matching
        vendor_name = vendor.get('vendor_name_canonical', '') or vendor.get('vendor_name_clean', '')

        # Apply rules
        dept, cat, desc, sugg, rule_id = engine.apply_rules(vendor_name)

        # Create output row with all original columns plus new ones
        output_row = vendor.copy()
        output_row['department_prefill'] = dept or ''
        output_row['category_prefill'] = cat or ''
        output_row['description_prefill'] = desc or ''
        output_row['suggestion_prefill'] = sugg or ''
        output_row['rule_id'] = rule_id or ''

        # Determine if needs LLM (any field is missing)
        needs_llm = not all([dept, cat, desc, sugg])
        output_row['needs_llm'] = 'True' if needs_llm else 'False'

        output_rows.append(output_row)

        if rule_id:
            matched_count += 1

        if needs_llm:
            needs_llm_count += 1
            llm_needed_rows.append(output_row)

    # Determine output columns
    if output_rows:
        output_columns = list(output_rows[0].keys())
    else:
        output_columns = []

    # Write all vendors to prefilled file
    print(f"\nWriting all vendors to: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(output_rows)

    # Write vendors needing LLM to separate file
    print(f"Writing vendors needing LLM to: {llm_needed_file}")
    with open(llm_needed_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(llm_needed_rows)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total vendors processed:      {len(vendors)}")
    print(f"Vendors matched by rules:     {matched_count} ({matched_count/len(vendors)*100:.1f}%)")
    print(f"Vendors needing LLM:          {needs_llm_count} ({needs_llm_count/len(vendors)*100:.1f}%)")
    print(f"\n✅ Successfully created:")
    print(f"   - {output_file}")
    print(f"   - {llm_needed_file}")
    print("=" * 70)


if __name__ == '__main__':
    apply_prefill_rules()
