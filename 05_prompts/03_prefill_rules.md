Create a deterministic prefill system with category tagging (working-only).

1) Create 02_working/prefill_rules.yml
- Define a controlled category list at the top:
  Cloud, CRM, Sales Engagement, Travel & Expense, Coworking/Office, Telecom,
  Recruiting, Audit/Tax, Legal Services, Productivity/Collab, Security/IT Ops,
  Marketing/SEO/PR, Product/Design, Finance Systems, General Ops, Other
- Add ~30 rules. Each rule must include:
  id, match_type (contains|regex), pattern,
  department (one of the 12 allowed),
  category (from the list),
  description_template (<= 15 words),
  suggestion (exactly one of: Consolidate, Terminate, Optimize costs),
  notes

2) Write 04_code/02_apply_prefill_rules.py that:
- reads 02_working/vendors_normalized.csv
- applies rules and outputs:
  02_working/vendors_prefilled.csv
  02_working/vendors_needing_llm.csv
- adds columns:
  department_prefill, category_prefill, description_prefill, suggestion_prefill, rule_id, needs_llm
- sets needs_llm = True if any of department/category/description/suggestion is missing

Validation:
- Department must be exactly one of the 12 allowed
- Suggestion must be exactly Consolidate/Terminate/Optimize costs
- Description <= 15 words
- Category must be from the controlled list (use Other if unsure)

Run the script and ensure both output files are created.
