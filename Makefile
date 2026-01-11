# Makefile for Vendor Analysis Pipeline
# Run Python scripts in 04_code/ in the correct order

PYTHON ?= python3
CODE_DIR := 04_code

.PHONY: all normalize prefill batches merge qa help clean

# Default target
all: normalize prefill batches merge qa
	@echo "Pipeline complete."

# Step 1: Normalize vendor names and identify aliases
normalize:
	@echo "==> Running normalize_vendors..."
	$(PYTHON) $(CODE_DIR)/01_normalize_vendors.py

# Step 2: Apply prefill rules to normalized vendors
prefill: normalize
	@echo "==> Running apply_prefill_rules..."
	$(PYTHON) $(CODE_DIR)/02_apply_prefill_rules.py

# Step 3: Generate batch input files for LLM processing
batches: prefill
	@echo "==> Running make_batches..."
	$(PYTHON) $(CODE_DIR)/02b_make_batches.py

# Step 4: Merge prefilled data with Claude batch results
merge: batches
	@echo "==> Running merge_results..."
	$(PYTHON) $(CODE_DIR)/03_merge_results.py

# Step 5: Run QA checks and generate reports
qa: merge
	@echo "==> Running qa_checks..."
	$(PYTHON) $(CODE_DIR)/04_qa_checks.py

# Show help
help:
	@echo "Vendor Analysis Pipeline Makefile"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  all        Run the full pipeline (normalize -> prefill -> batches -> merge -> qa)"
	@echo "  normalize  Step 1: Normalize vendor names and identify aliases"
	@echo "  prefill    Step 2: Apply prefill rules to normalized vendors"
	@echo "  batches    Step 3: Generate batch input files for LLM processing"
	@echo "  merge      Step 4: Merge prefilled data with Claude batch results"
	@echo "  qa         Step 5: Run QA checks and generate reports"
	@echo "  clean      Remove generated files in 02_working/ and 03_outputs/"
	@echo "  help       Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make all           # Run full pipeline"
	@echo "  make normalize     # Run only normalization step"
	@echo "  make qa            # Run full pipeline (qa depends on all prior steps)"

# Clean generated outputs
clean:
	@echo "==> Cleaning generated files..."
	rm -f 02_working/*.csv
	rm -f 03_outputs/*.csv
	rm -f 03_outputs/*.md
	rm -rf 03_outputs/01_claude_batches/
	@echo "Clean complete."
