Set up a GitHub-friendly, numbered repo structure for a vendor spend diligence assessment.

Important constraints:
- GitHub cannot display empty folders, so every folder must contain at least one committed file.
- Create a small README.md inside each folder describing what belongs there (3–6 lines).
- Use numbered directories so GitHub alphabetical sorting preserves workflow order.

Create:
00_admin/README.md
01_inputs/README.md
02_working/README.md
02_working/01_batches/README.md
03_outputs/README.md
03_outputs/01_claude_batches/README.md
04_code/README.md
05_prompts/README.md
06_docs/README.md
.github/workflows/.gitkeep

Also create a root README.md with placeholders for:
- Objective
- Deliverables (Google Sheet link placeholder, Memo link placeholder)
- Repo structure
- Methodology overview (placeholder)
- Reproduce steps (placeholder)
- QA approach (placeholder)
- Notes/assumptions

After creating files, print a tree of the created paths.
