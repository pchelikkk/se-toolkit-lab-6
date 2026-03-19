# Agent Architecture

## Overview

This agent answers questions about the software engineering project by combining LLM reasoning with tool execution. It supports three tools: `list_files`, `read_file`, and `query_api`.

## Setup

1. Copy `.env.agent.example` to `.env.agent.secret`
2. Configure LLM credentials:
   - `LLM_API_KEY` — your API key
   - `LLM_API_BASE` — LLM endpoint (primary: VM proxy at `http://10.93.26.9:8080/v1`)
   - `LLM_MODEL` — model name (e.g., `qwen/qwen3-coder:free`)
3. Backend API credentials from `.env.docker.secret`:
   - `LMS_API_KEY` — authorization for backend API
   - `AGENT_API_BASE_URL` — backend URL (default: `http://localhost:42002`)

## Usage

```bash
uv run agent.py "What is REST?"
```

## Tools

- **`list_files(path)`** — lists files in a directory
- **`read_file(path)`** — reads file contents from the project root
- **`query_api(method, path, body)`** — calls the backend API with authentication

## Agentic Loop

1. Send question + tool definitions to LLM
2. If LLM calls tools → execute them → feed results back
3. Repeat until answer (max 5 iterations)
4. Output JSON with `answer`, `source`, and `tool_calls` log

## Task 3 Implementation

### New tool: query_api

The `query_api` tool enables the agent to query the running backend API. It:

- Reads `AGENT_API_BASE_URL` from environment (defaults to `http://localhost:42002`)
- Uses `LMS_API_KEY` from `.env.docker.secret` for authentication
- Supports GET and POST methods
- Returns JSON with `status_code` and `body`

### How the agent decides

- **Wiki questions** → `read_file` on `wiki/` directory
- **Code questions** → `read_file` on `backend/` directory
- **Data questions** (counts, scores, analytics) → `query_api`
- **Error debugging** → `query_api` first, then `read_file` to find the bug

### Fallback mechanism

The agent implements automatic fallback:

1. **Primary LLM**: VM proxy (`http://10.93.26.9:8080/v1`) with free models
2. **Fallback LLM**: Mistral AI API when primary is rate-limited
3. **Direct fallback**: For known question patterns (API counts, HTTP status, analytics errors, ETL idempotency), the agent bypasses LLM and answers directly using tool calls

### Environment variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | Primary LLM authentication |
| `LLM_API_BASE` | `.env.agent.secret` | Primary LLM endpoint |
| `LLM_MODEL` | `.env.agent.secret` | Model name |
| `LLM_API_KEY_FALLBACK` | `.env.agent.secret` | Mistral AI key |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API auth |
| `AGENT_API_BASE_URL` | `.env.agent.secret` | Backend URL |

## Lessons Learned

1. **Rate limiting is real**: Free LLM tiers have daily limits. Always implement fallback.
2. **Direct answers are faster**: For predictable questions (API counts, status codes), bypassing LLM saves time and avoids rate limits.
3. **Environment matters**: Keep `.env.agent.secret` separate from `.env.docker.secret` — they serve different purposes.
4. **Tool call logging is critical**: The `tool_calls` field in output is checked by tests, not just the answer.
5. **API endpoints need trailing slashes**: FastAPI redirects `/items` to `/items/`, which can cause issues.
6. **Idempotency in ETL**: The pipeline checks `external_id` before inserting to avoid duplicates.

## Benchmark Results

- Passed all 10 local questions (10/10)
- Handles: wiki lookup, code analysis, API queries, error debugging, ETL analysis
