#!/usr/bin/env python3
"""
Generate batch input files for LLM processing.

Reads vendors_needing_llm.csv and splits it into smaller batch files
for processing. Also creates a manifest file tracking batch metadata.
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Dict


def read_vendors(input_file: Path) -> List[Dict[str, str]]:
    """Read vendors needing LLM processing."""
    vendors = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendors.append(row)
    return vendors


def write_batch_file(batch_file: Path, vendors: List[Dict[str, str]]) -> None:
    """Write a batch input file with vendor_name_raw and spend_usd."""
    with open(batch_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['vendor_name_raw', 'spend_usd'])
        for vendor in vendors:
            writer.writerow([vendor['vendor_name_raw'], vendor['spend_usd']])


def write_manifest(manifest_file: Path, batches: List[Dict]) -> None:
    """Write the batch manifest file."""
    with open(manifest_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'batch_id', 'input_file', 'row_start', 'row_end',
            'vendor_count', 'total_spend'
        ])
        writer.writeheader()
        writer.writerows(batches)


def create_batches(input_file: Path, output_dir: Path, batch_size: int) -> None:
    """Create batch files and manifest."""
    # Read all vendors
    vendors = read_vendors(input_file)
    total_vendors = len(vendors)

    print(f"Read {total_vendors} vendors needing LLM processing")

    if total_vendors == 0:
        print("No vendors to process. Exiting.")
        return

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created output directory: {output_dir}")

    # Split into batches
    batches = []
    batch_num = 1
    row_start = 1  # Start at 1 (assuming CSV header is row 0)

    for i in range(0, total_vendors, batch_size):
        batch_vendors = vendors[i:i + batch_size]
        batch_id = f"batch_{batch_num:03d}"
        batch_file = output_dir / f"{batch_id}_input.csv"

        # Write batch file
        write_batch_file(batch_file, batch_vendors)

        # Calculate batch metadata
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

        print(f"Created {batch_id}: {len(batch_vendors)} vendors (rows {row_start}-{row_end})")

        batch_num += 1
        row_start = row_end + 1

    # Write manifest
    manifest_file = output_dir / 'batch_manifest.csv'
    write_manifest(manifest_file, batches)
    print(f"\nCreated manifest: {manifest_file}")
    print(f"Total batches: {len(batches)}")
    print(f"Total vendors: {total_vendors}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate batch input files for LLM processing'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of vendors per batch (default: 50)'
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

    # Validate inputs
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.batch_size < 1:
        print(f"Error: Batch size must be at least 1", file=sys.stderr)
        sys.exit(1)

    # Create batches
    create_batches(args.input, args.output_dir, args.batch_size)
    print("\nBatch generation complete!")


if __name__ == '__main__':
    main()
