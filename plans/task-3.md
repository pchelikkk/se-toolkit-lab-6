# Task 3 Plan

## Goal

Add `query_api` tool to answer system questions (framework, ports, status codes) and data queries (item count, scores).

## New Tool: `query_api`

### Parameters

- `method` - HTTP method (GET, POST, etc.)
- `path` - API endpoint (e.g., `/items/`, `/analytics/completion-rate`)
- `body` - optional JSON request body

### Returns

JSON string with `status_code` and `body`.

### Authentication

Use `LMS_API_KEY` from `.env.docker.secret` (separate from `LLM_API_KEY`).

## Environment Variables

| Variable | Purpose | Source |
| --- | --- | --- |
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (default: `http://localhost:42002`) | Optional |

## System Prompt Updates

Update prompt to tell LLM when to use each tool:

- `read_file` - wiki instructions, code, Docker files, ETL logic
- `list_files` - structure discovery
- `query_api` - runtime behavior, item counts, status codes, API errors

## Agent Loop Hardening

- Handle `content: null` from tool-calling responses: `msg.get("content") or ""`
- Keep tool call log for debugging
- Truncate long tool outputs to prevent loops

## Tests

Add 2 regression tests:

1. Framework question → must use `read_file`
2. Item count question → must use `query_api`

Use stub LLM for deterministic tests.

## Benchmark Strategy

Run `uv run run_eval.py` and iterate:

1. Fix wrong tool choice
2. Fix unclear tool schema
3. Fix wrong API path or params
4. Tighten system prompt

## Files

- `agent.py` - add `query_api` tool, update system prompt, harden loop
- `AGENT.md` - document `query_api` tool and lessons learned (200+ words)
- `tests/test_agent.py` - add 2 tool-selection tests
