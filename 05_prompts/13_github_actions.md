Create .github/workflows/qa.yml that runs on push and pull_request:

- Set up Python 3.11
- Install minimal deps if needed
- Run:
  make normalize
  make prefill
  make batches
  make merge
  make qa

If 03_outputs/01_claude_batches/ has no batch files, fail with a clear message explaining Claude batches must be generated first.

Output the full YAML.
