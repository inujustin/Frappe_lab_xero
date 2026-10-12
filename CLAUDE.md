@AGENTS.md

## Claude Code specifics

- The import above loads AGENTS.md; it is the contract.
- Skills live in `.agents/skills/<name>/SKILL.md`. When the prompt names one, read that file and follow it.
- One session, one job. Do not use subagents or background tasks.
- Do not ask to change permissions or settings; report BLOCKED instead.
