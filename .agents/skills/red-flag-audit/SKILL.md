---
name: red-flag-audit
description: Read-only scan of the custom apps for the project's red-flag patterns and structure rules (permission bypasses, raw SQL, commits, endpoints without a permission check, layer violations), returning a findings list. Use when asked to audit, scan or lint the codebase for rule violations.
---

# Red-flag audit

You search and report. You edit nothing and run no scripts or linters; use the file search and read tools only. The scope is the custom apps named in AGENTS.md Part B, never the framework folders.

## Steps

1. Read `AGENTS.md` Part B (coding rules and red flags). If the prompt names an app or folder, audit only that.
2. Search for every red-flag pattern in Part B and in `.agents/skills/code-reviewer/SKILL.md`. Open each hit and read enough around it to judge it.
3. Check the structure rules that a text search cannot settle:
   - **Every action has an auth/permission element:** list each `@frappe.whitelist` function. For each, name the line where permission is enforced (document permission check, role check, the project's guard decorator, or a permission-aware query). None found = finding.
   - **Whitelist hygiene:** `allow_guest=True`, missing `methods=`, parameters without type hints.
   - **Layers:** imports that go against the layer direction in Part B (for example domain code importing an interface or infrastructure module).
   - **Hooks:** handler logic written inside `hooks.py`, or one events file serving several domains.
   - **Schema outside code:** DDL statements, or code that creates fields or DocTypes at runtime instead of through the documented path.
   - **External calls in a request:** HTTP calls to Xero or other services outside `tasks/` or a background job.
4. Judge each hit: `violation`, `acceptable` (say why, for example it is inside `patches/`), or `needs human`.
5. Print the output and stop. Do not fix anything; fixes are separate requests.

## Output (exactly this shape)

```
# Red-flag audit: <scope>
Files searched: <count or globs>
Findings:
1. [violation|needs human] <rule id> path/file.py:42 — what — what to do
Acceptable hits: <rule id path:line — why>, ...
Endpoints: <n> whitelisted, <m> without a visible permission check (listed above)
Not checked: <rules you could not check and why>
```
No praise and no summary of what the code does. If there are no findings, say which patterns were searched.
