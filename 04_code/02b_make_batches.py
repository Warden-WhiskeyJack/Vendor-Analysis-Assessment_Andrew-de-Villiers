#!/usr/bin/env python3
"""
Generate Batch Input Files for LLM Processing.

Purpose:
    Splits the vendors needing LLM classification into smaller batch files.
    This enables parallel LLM processing and provides checkpointing for
    large vendor lists. Creates a manifest to track batch metadata.

Inputs:
    - 02_working/vendors_needing_llm.csv: Vendors requiring LLM classification
      (output from 02_apply_prefill_rules.py)

Outputs:
    - 02_working/01_batches/batch_NNN_input.csv: Individual batch files containing:
        * vendor_name_raw: Original vendor name
        * spend_usd: Annual spend amount
    - 02_working/01_batches/batch_manifest.csv: Manifest tracking:
        * batch_id, input_file, row_start, row_end, vendor_count, total_spend

Algorithm:
    1. Read all vendors needing LLM processing
    2. Split into chunks of --batch-size vendors (default: 50)
    3. Write each batch to a separate CSV file
    4. Generate manifest with metadata for each batch

How to run:
    python 04_code/02b_make_batches.py
    python 04_code/02b_make_batches.py --batch-size 100
    python 04_code/02b_make_batches.py --input custom_input.csv --output-dir custom_dir/
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Dict

# =============================================================================
# Constants
# =============================================================================

# Default batch size. 50 balances LLM context limits with processing efficiency.
# Smaller batches = more files but easier to retry failures.
# Larger batches = fewer files but risk losing more work on failure.
DEFAULT_BATCH_SIZE = 50


# =============================================================================
# File I/O Functions
# =============================================================================

def read_vendors(input_file: Path) -> List[Dict[str, str]]:
    """
    Read vendors needing LLM processing from CSV.

    Args:
        input_file: Path to vendors_needing_llm.csv.

    Returns:
        List of vendor dictionaries.
    """
    vendors = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendors.append(row)
    return vendors


def write_batch_file(batch_file: Path, vendors: List[Dict[str, str]]) -> None:
    """
    Write a batch input file with minimal columns for LLM processing.

    Args:
        batch_file: Path to output batch file.
        vendors: List of vendor records to write.
    """
    with open(batch_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['vendor_name_raw', 'spend_usd'])
        for vendor in vendors:
            writer.writerow([vendor['vendor_name_raw'], vendor['spend_usd']])


def write_manifest(manifest_file: Path, batches: List[Dict]) -> None:
    """
    Write the batch manifest file for tracking processing status.

    Args:
        manifest_file: Path to manifest CSV.
        batches: List of batch metadata dictionaries.
    """
    with open(manifest_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'batch_id', 'input_file', 'row_start', 'row_end',
            'vendor_count', 'total_spend'
        ])
        writer.writeheader()
        writer.writerows(batches)


# =============================================================================
# Batch Creation Logic
# =============================================================================

def create_batches(input_file: Path, output_dir: Path, batch_size: int) -> int:
    """
    Create batch files and manifest from vendor input.

    Args:
        input_file: Path to vendors_needing_llm.csv.
        output_dir: Directory to write batch files.
        batch_size: Number of vendors per batch.

    Returns:
        Number of batches created.
    """
    # Read all vendors
    vendors = read_vendors(input_file)
    total_vendors = len(vendors)

    print(f"Read {total_vendors} vendors needing LLM processing")

    if total_vendors == 0:
        print("No vendors to process.")
        return 0

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Split into batches
    batches: List[Dict] = []
    batch_num = 1
    row_start = 1  # 1-indexed row numbers (header is row 0)

    for i in range(0, total_vendors, batch_size):
        batch_vendors = vendors[i:i + batch_size]
        batch_id = f"batch_{batch_num:03d}"
        batch_file = output_dir / f"{batch_id}_input.csv"

        # Write batch file
        write_batch_file(batch_file, batch_vendors)

        # Calculate batch metadata for manifest
        row_end = row_start + len(batch_vendors) - 1
        total_spend = sum(float(v['spend_usd']) for v in batch_vendors)

        batches.append({
            'batch_id': batch_id,
            'input_file': f"{batch_id}_input.csv",
            'row_start': row_start,
            'row_end': row_end,
            'vendor_count': len(batch_vendors),
            'total_spend': f"{total_spend:.2f}"
        })

        print(f"  {batch_id}: {len(batch_vendors)} vendors, ${total_spend:,.0f} spend")

        batch_num += 1
        row_start = row_end + 1

    # Write manifest for tracking batch processing status
    manifest_file = output_dir / 'batch_manifest.csv'
    write_manifest(manifest_file, batches)

    return len(batches)


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """
    Main entry point for batch generation.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description='Generate batch input files for LLM processing'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f'Number of vendors per batch (default: {DEFAULT_BATCH_SIZE})'
    )
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('02_working/vendors_needing_llm.csv'),
        help='Input CSV file (default: 02_working/vendors_needing_llm.csv)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('02_working/01_batches'),
        help='Output directory for batch files (default: 02_working/01_batches)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("BATCH FILE GENERATION")
    print("=" * 60)

    # Validate inputs
    if not args.input.exists():
        print(f"\nERROR: Input file not found: {args.input}")
        print("  Run 02_apply_prefill_rules.py first to generate this file.")
        return 1

    if args.batch_size < 1:
        print(f"\nERROR: Batch size must be at least 1 (got {args.batch_size})")
        return 1

    print(f"\nInput file: {args.input}")
    print(f"Batch size: {args.batch_size} vendors per batch")

    # Create batches
    num_batches = create_batches(args.input, args.output_dir, args.batch_size)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Batches created: {num_batches}")
    print(f"Output directory: {args.output_dir}")
    print(f"Manifest file: {args.output_dir / 'batch_manifest.csv'}")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
