# Agent

## What this agent does

This agent answers questions about the repository **and** the running learning-management system. It is no longer just a wiki reader. It can now inspect source code, discover project structure, and send authenticated HTTP requests to the deployed backend.

The design follows a simple rule: use the **right source of truth** for the question. If the user asks about instructions from the wiki, branch protection, SSH, Docker wiring, or ETL logic, the agent should read repository files. If the user asks what the system currently returns, how many items exist, which status code an endpoint produces, or what error appears for a bad analytics query, the agent should use the live API.

## Environment and authentication

All configuration is read from environment variables rather than hardcoded constants. The agent loads local values from `.env.agent.secret`, `.env.docker.secret`, and `.env` only as a convenience for development.

Required variables:

- `LLM_API_KEY` — authentication for the LLM provider
- `LLM_API_BASE` — OpenAI-compatible base URL for the LLM endpoint
- `LLM_MODEL` — model name
- `LMS_API_KEY` — backend API key for the LMS service
- `AGENT_API_BASE_URL` — backend base URL, defaulting to `http://localhost:42002`

The split between keys matters. `LLM_API_KEY` is used only for the model call. `LMS_API_KEY` is sent as `Authorization: Bearer <key>` by the `query_api` tool when talking to the backend.

## Tools

### `list_files(path)`

Lists directory contents inside the repository. This is useful for questions like “list all router modules” or when the model first needs to discover where a file lives.

### `read_file(path)`

Reads a repository text file. This is the main tool for wiki instructions, FastAPI source code, `docker-compose.yml`, the backend `Dockerfile`, and the ETL implementation.

### `query_api(method, path, params=None)`

Calls the running LMS API with Bearer authentication. This is the main tool for runtime questions, including:

- current item counts
- real auth failures
- status codes
- analytics errors on missing or bad data
- reproducing a failure before reading the code that caused it

## Tool-selection policy

The system prompt explicitly teaches the LLM how to choose tools:

- use `read_file` for static documentation and source-code facts
- use `list_files` to explore the repo first when needed
- use `query_api` for live system behavior
- for debugging, reproduce with `query_api` first and then inspect code with `read_file`

That distinction is important for hidden benchmark questions. Documentation may describe intended behavior, but the running backend is the ground truth for actual responses and crashes.

## Reliability improvements

The agent loop now handles `content: null` safely during tool-calling turns, records all tool calls for evaluation, truncates oversized tool outputs to reduce looping, and infers a `source` path from the last file-based tool call.

## Benchmark notes and lessons learned

In this environment I could not run the full live benchmark because the required secrets and services were not available. Still, the main expected failure modes were clear from the original code: missing `query_api`, missing dependency declarations for `requests` and `python-dotenv`, weak tool descriptions, and no guidance about when to trust files versus the running system.

The biggest lesson from Task 3 is that agent quality depends less on “more prompting” and more on choosing the correct source of truth and giving the model precise tool boundaries. A system agent must be able to switch between documentation lookup, code inspection, and live runtime inspection without confusing those layers.

## Final local eval score

Not executed in this container because the live autochecker credentials and running services were unavailable here. The repository is prepared so you can run the real check locally with:

```bash
uv run run_eval.py
```
