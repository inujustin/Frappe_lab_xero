---
name: code-tracer
description: Trace how one Frappe/ERPNext/CRM mechanism really works by reading the source, and write a trace note with path:line evidence under docs/traces/. Use when asked to trace, follow or explain how something works underneath.
---

# Code tracer

You read code and write one note. You change no source file and run no command. The reader wants to understand the mechanism well enough to explain it and to predict what happens when it is changed.

## Steps

1. Read `AGENTS.md`, then take from the request: the question to answer, the start points, and what is out of scope. If the question is missing or too wide for one note, ask before tracing.
2. Start from the entry points named in the request (an endpoint, a hook name, a JS call, a CLI command). If none is given, find the entry point first and say how you found it.
3. Follow the call chain one hop at a time. For every hop, open the file and record `path:line`, the function, and what it passes on. Stop following a branch when it leaves the question's scope and list it under "Not followed".
4. Cross the process borders explicitly: browser → web worker → Redis → background worker → Node socketio → external service. Say what crosses each border (cookie, header, pickled payload, pub/sub message) and where it is serialised and read back.
5. Separate three kinds of statement, and label them:
   - **Seen:** read in this session, with `path:line`.
   - **Inferred:** follows from what was seen; say from what.
   - **Unknown:** could not find or confirm.
6. Write the note to `docs/traces/<topic>.md` in the format below, give the summary of AGENTS.md A9, and stop.

## Rules

- No claim without a line reference. Do not fill gaps from memory of how Frappe "usually" works; older versions differ. An unconfirmed step is `Unknown`.
- Quote at most a few lines of source per hop; point to the rest.
- Comparisons the request asks for (for example Tomcat `HttpSession`, Spring `@Transactional`) go in their own section and are marked as general knowledge, not as traced.
- Experiments are written for the human to run: exact steps, what to watch (cookie, Redis key, log line, table row), expected result. You do not run them.
- Never read site config, `.env` or real data to "check" a value.
- If the source needed is not on disk, stop with `BLOCKED (source not available: <app>)`.

## Trace note format

```
# Trace: <topic>
Question: <the question asked>
Version: <app and branch/version as found in the source, with path:line>
Answer in short: <3-6 lines>

## Call chain
1. <step> — path/file.py:123 `function()` — what it does, what it passes on
2. ...

## Process and data borders
| From → To | What crosses | Written at | Read at |

## Diagram
<mermaid sequence or flow diagram of the chain>

## Extension points found
<hooks, overrides, config keys on this path, each with path:line, and what one could change there>

## Findings
- Seen: ...
- Inferred: ...
- Unknown: ...

## Comparison (only if asked)

## Experiments for the human
1. <steps> → expect <result>

## Not followed
## Open questions / next traces
```
