# Task 3 Plan

## What's new
Adding `query_api` tool so agent can talk to backend.

## How it works
- Same loop as task 2
- New tool calls backend using LMS_API_KEY
- Agent chooses: wiki (read_file) vs code (read_file) vs API (query_api)

## Tools
Same as before + new one:
- `query_api(method, path, body)` - calls backend, returns status + body

## Environment
- LLM stuff from `.env.agent.secret`
- LMS_API_KEY from `.env.docker.secret` 
- API base URL from `AGENT_API_BASE_URL` (default localhost:42002)

## How agent decides
- Wiki questions → read_file on wiki/
- Code questions → read_file on backend/  
- Data questions (counts, scores) → query_api
- Errors → query_api then read_file

## Benchmark
Run `uv run run_eval.py`, fix failing ones, repeat until all pass.
