---
name: runbook-writer
description: Write a reusable step-by-step guide (runbook) for a human to run, such as bringing up a dev environment, migrating, deploying, backing up or a git workflow, without executing anything. Use when asked to write or update a runbook.
---

# Runbook writer

A runbook is a guide a human runs by hand, again and again. You write it; you never run it.

## Steps

1. Start from `docs/runbooks/_TEMPLATE.md` (or the folder named in the request).
2. Read the repo (config files, README, existing runbooks) to get real paths, names and versions. Do not guess commands: if something can't be confirmed from the repo, mark it `VERIFY:` for the human.
3. Fill every section. Each step: what it does in one line, where it runs (`Run in: host` or `container <name>`; never assume they share files, tools or paths), the exact command in a code block, and what the human should see if it worked.
4. Mark every step that changes data, a database, a server or a git branch with `⚠️ CHANGES STATE`, and give its rollback.
5. Use placeholders for anything secret or environment-specific: `<SITE_NAME>`, `<DB_ROOT_PASSWORD>`. Never copy a real secret, even if you saw one.
6. Add the runbook to the index table in `docs/runbooks/README.md`.

## Never

- Execute any command from the runbook, including "harmless" checks.
- Write a step that pipes a remote script into a shell without saying so in a warning.
