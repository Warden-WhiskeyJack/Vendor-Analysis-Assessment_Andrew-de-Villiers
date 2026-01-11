Write 04_code/02b_make_batches.py (Python) that:
- reads 02_working/vendors_needing_llm.csv
- writes batch input files to 02_working/01_batches/ as:
  batch_001_input.csv, batch_002_input.csv, ...
Each batch input contains:
  vendor_name_raw, spend_usd

Also write 02_working/01_batches/batch_manifest.csv with:
  batch_id, input_file, row_start, row_end, vendor_count, total_spend

Default batch size = 50; configurable with a CLI arg.

Run it and ensure the batch files + manifest are created.
