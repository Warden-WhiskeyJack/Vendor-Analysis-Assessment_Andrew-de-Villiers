"""
Vendor Name Normalization Script

Purpose:
    Normalizes vendor names from raw input data and identifies potential alias
    relationships based on string similarity. This helps identify duplicate vendors
    or variations of the same vendor name.

Inputs:
    - 01_inputs/vendors_raw.csv: Raw vendor data with columns:
        * Vendor Name
        * Department
        * Last 12 months Cost (USD)
        * 1-line Description on what the Vendor does
        * Suggestions (Consolidate / Terminate / Optimize costs)

Outputs:
    - 02_working/vendors_normalized.csv: Normalized vendor data with columns:
        * vendor_name_raw: Original vendor name from input
        * spend_usd: Parsed spend amount as float
        * vendor_name_clean: Lowercase, normalized punctuation, collapsed whitespace
        * vendor_name_canonical: Further normalized by removing legal suffixes

    - 02_working/vendor_alias_map.csv: Potential vendor aliases with columns:
        * canonical_name: Base vendor name
        * alias_name: Similar vendor name (potential alias)
        * similarity_score: Similarity percentage (only >= 92)

Algorithm:
    1. Parse raw CSV and extract vendor names and spend
    2. Clean vendor names: lowercase, normalize punctuation, collapse whitespace
    3. Create canonical names: strip legal suffixes (ltd, llc, inc, gmbh, d.o.o., etc.)
    4. Find similar vendor pairs using fuzzy string matching (>= 92% similarity)
    5. Output normalized data and alias mappings

Dependencies:
    - Standard library: csv, pathlib, re, string
    - Optional: rapidfuzz (for faster fuzzy matching)
        Install with: pip install rapidfuzz
        Falls back to difflib if rapidfuzz not available

How to run:
    python 04_code/01_normalize_vendors.py

    Ensure the input file exists at: 01_inputs/vendors_raw.csv
    Output files will be created at: 02_working/
"""

import csv
import re
import string
from pathlib import Path
from typing import List, Tuple, Dict

# Try to import rapidfuzz, fall back to difflib if not available
try:
    from rapidfuzz import fuzz
    USE_RAPIDFUZZ = True
    print("Using rapidfuzz for similarity matching (faster)")
except ImportError:
    import difflib
    USE_RAPIDFUZZ = False
    print("rapidfuzz not found - using difflib for similarity matching")
    print("For better performance, install rapidfuzz: pip install rapidfuzz")
    print()


# Define paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_FILE = PROJECT_ROOT / "01_inputs" / "vendors_raw.csv"
OUTPUT_NORMALIZED = PROJECT_ROOT / "02_working" / "vendors_normalized.csv"
OUTPUT_ALIAS_MAP = PROJECT_ROOT / "02_working" / "vendor_alias_map.csv"

# Legal suffixes to strip for canonical names (case-insensitive)
LEGAL_SUFFIXES = [
    'limited', 'ltd', 'llc', 'inc', 'incorporated', 'corp', 'corporation',
    'gmbh', 'd.o.o', 'doo', 's.r.o', 'sro', 'a/s', 'aps', 'ag', 'sa',
    'b.v', 'bv', 'n.v', 'nv', 'pty', 'pte', 'pvt', 's.l', 'sl',
    'llp', 'lp', 'plc', 'p.c', 'pc', 'co', 'company', 'companies',
    'j.d.o.o', 'jdoo', 'obrt', 'vl', 'bvba', 'd.d', 'dd'
]

# Minimum similarity score for alias detection
SIMILARITY_THRESHOLD = 92.0


def parse_currency(value: str) -> float:
    """
    Parse currency string to float.

    Args:
        value: Currency string like "$3,117,226" or "$1,001"

    Returns:
        Float value, or 0.0 if parsing fails
    """
    if not value or not isinstance(value, str):
        return 0.0

    # Remove currency symbols, commas, and whitespace
    cleaned = value.strip().replace('$', '').replace(',', '').replace(' ', '')

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def normalize_punctuation(text: str) -> str:
    """
    Normalize punctuation in text.
    - Convert special quotes/apostrophes to standard ASCII
    - Normalize dashes and hyphens
    - Remove other special characters but keep basic punctuation

    Args:
        text: Input text

    Returns:
        Text with normalized punctuation
    """
    # Normalize quotes and apostrophes
    text = text.replace(''', "'").replace(''', "'").replace('"', '"').replace('"', '"')

    # Normalize dashes to standard hyphen
    text = text.replace('–', '-').replace('—', '-')

    # Replace other special punctuation with space
    for char in text:
        if char not in string.ascii_letters + string.digits + " .,&()-'\"":
            text = text.replace(char, ' ')

    return text


def clean_vendor_name(name: str) -> str:
    """
    Clean vendor name: lowercase, normalize punctuation, collapse whitespace.

    Args:
        name: Raw vendor name

    Returns:
        Cleaned vendor name
    """
    if not name or not isinstance(name, str):
        return ""

    # Strip leading/trailing whitespace
    name = name.strip()

    # Lowercase
    name = name.lower()

    # Normalize punctuation
    name = normalize_punctuation(name)

    # Collapse multiple spaces to single space
    name = re.sub(r'\s+', ' ', name)

    # Strip again after processing
    name = name.strip()

    return name


def create_canonical_name(cleaned_name: str) -> str:
    """
    Create canonical vendor name by stripping legal suffixes and extra punctuation.

    Args:
        cleaned_name: Already cleaned vendor name

    Returns:
        Canonical vendor name
    """
    if not cleaned_name:
        return ""

    canonical = cleaned_name

    # Remove content in parentheses (often subsidiaries or descriptions)
    canonical = re.sub(r'\([^)]*\)', '', canonical)

    # Remove trailing/leading punctuation and whitespace
    canonical = canonical.strip(' .,;:-')

    # Try to remove legal suffixes (working from the end)
    words = canonical.split()

    # Check last few words for legal suffixes
    while words:
        last_word = words[-1].strip('.,;:-')
        if last_word in LEGAL_SUFFIXES:
            words.pop()
        else:
            break

    canonical = ' '.join(words)

    # Clean up any remaining multiple spaces
    canonical = re.sub(r'\s+', ' ', canonical).strip()

    # Remove trailing punctuation again
    canonical = canonical.strip(' .,;:-')

    return canonical


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings.

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity score (0-100)
    """
    if USE_RAPIDFUZZ:
        return fuzz.ratio(str1, str2)
    else:
        # Use difflib's SequenceMatcher
        ratio = difflib.SequenceMatcher(None, str1, str2).ratio()
        return ratio * 100


def find_aliases(vendors: List[Dict]) -> List[Tuple[str, str, float]]:
    """
    Find potential vendor aliases based on canonical name similarity.

    Args:
        vendors: List of vendor dictionaries with canonical names

    Returns:
        List of tuples (canonical_name, alias_name, similarity_score)
        Only includes pairs with similarity >= SIMILARITY_THRESHOLD
    """
    aliases = []

    # Group vendors by canonical name
    canonical_groups = {}
    for vendor in vendors:
        canonical = vendor['vendor_name_canonical']
        if canonical not in canonical_groups:
            canonical_groups[canonical] = []
        canonical_groups[canonical].append(vendor)

    # Get unique canonical names sorted for consistent comparison
    canonical_names = sorted(canonical_groups.keys())

    # Compare each pair of canonical names
    total_comparisons = len(canonical_names) * (len(canonical_names) - 1) // 2
    print(f"Comparing {len(canonical_names)} unique canonical names ({total_comparisons:,} pairs)...")

    for i, canonical1 in enumerate(canonical_names):
        if i % 20 == 0 and i > 0:
            print(f"  Progress: {i}/{len(canonical_names)} canonical names processed...")

        for canonical2 in canonical_names[i+1:]:
            # Skip if they're identical
            if canonical1 == canonical2:
                continue

            # Calculate similarity
            similarity = calculate_similarity(canonical1, canonical2)

            # If similarity meets threshold, record as potential alias
            if similarity >= SIMILARITY_THRESHOLD:
                aliases.append((canonical1, canonical2, similarity))

    print(f"  Found {len(aliases)} potential alias pairs (>= {SIMILARITY_THRESHOLD}% similar)")

    return aliases


def main():
    """Main execution function."""

    print("=" * 70)
    print("VENDOR NAME NORMALIZATION SCRIPT")
    print("=" * 70)
    print()

    # Check input file exists
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        print("Please ensure vendors_raw.csv exists in 01_inputs/")
        return 1

    print(f"Input file: {INPUT_FILE}")
    print()

    # Create output directory if it doesn't exist
    OUTPUT_NORMALIZED.parent.mkdir(parents=True, exist_ok=True)

    # Read and process input data
    print("Reading and processing vendor data...")
    vendors = []

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                vendor_name_raw = row.get(' Vendor Name ', '').strip()  # Note: spaces before and after
                spend_str = row.get('Last 12 months Cost (USD)', '')

                # Skip empty rows
                if not vendor_name_raw:
                    continue

                # Parse spend
                spend_usd = parse_currency(spend_str)

                # Clean and canonicalize vendor name
                vendor_name_clean = clean_vendor_name(vendor_name_raw)
                vendor_name_canonical = create_canonical_name(vendor_name_clean)

                vendors.append({
                    'vendor_name_raw': vendor_name_raw,
                    'spend_usd': spend_usd,
                    'vendor_name_clean': vendor_name_clean,
                    'vendor_name_canonical': vendor_name_canonical
                })

    except Exception as e:
        print(f"ERROR reading input file: {e}")
        return 1

    print(f"  Processed {len(vendors)} vendor records")
    print()

    # Write normalized vendors CSV
    print(f"Writing normalized vendors to: {OUTPUT_NORMALIZED}")
    try:
        with open(OUTPUT_NORMALIZED, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['vendor_name_raw', 'spend_usd', 'vendor_name_clean', 'vendor_name_canonical']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(vendors)
        print("  ✓ Successfully wrote vendors_normalized.csv")
    except Exception as e:
        print(f"ERROR writing normalized vendors: {e}")
        return 1

    print()

    # Find aliases
    print("Identifying potential vendor aliases...")
    aliases = find_aliases(vendors)
    print()

    # Write alias map CSV
    print(f"Writing alias map to: {OUTPUT_ALIAS_MAP}")
    try:
        with open(OUTPUT_ALIAS_MAP, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['canonical_name', 'alias_name', 'similarity_score']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for canonical_name, alias_name, similarity_score in aliases:
                writer.writerow({
                    'canonical_name': canonical_name,
                    'alias_name': alias_name,
                    'similarity_score': f"{similarity_score:.2f}"
                })
        print(f"  ✓ Successfully wrote vendor_alias_map.csv with {len(aliases)} alias pairs")
    except Exception as e:
        print(f"ERROR writing alias map: {e}")
        return 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()

    # Summary statistics
    total_vendors = len(vendors)
    total_spend = sum(v['spend_usd'] for v in vendors)

    print(f"Total vendor records: {total_vendors}")
    print(f"Total spend: ${total_spend:,.2f}")
    print(f"Potential alias links: {len(aliases)} pairs with similarity >= {SIMILARITY_THRESHOLD}%")
    print()

    # Top 20 vendors by spend
    print("Top 20 Vendors by Spend:")
    print("-" * 70)

    sorted_vendors = sorted(vendors, key=lambda x: x['spend_usd'], reverse=True)

    for i, vendor in enumerate(sorted_vendors[:20], 1):
        print(f"{i:2d}. ${vendor['spend_usd']:>12,.2f}  {vendor['vendor_name_raw']}")

    print()
    print("=" * 70)
    print("NORMALIZATION COMPLETE")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    exit(main())
