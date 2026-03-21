# Task 3 Plan

## Goal

Turn the documentation agent into a system agent that can answer both repository questions and live backend questions.

## Implementation plan

### 1. Add a new `query_api` tool

I will define a third function-calling schema in `agent.py`:

- `method` — HTTP method, usually `GET`
- `path` — backend path such as `/items/` or `/analytics/completion-rate`
- `params` — optional query parameters like `{"lab": "lab-99"}`

The tool will call the deployed backend through `AGENT_API_BASE_URL` and authenticate with:

```text
Authorization: Bearer <LMS_API_KEY>
```

This keeps the backend key separate from the LLM provider key.

### 2. Read all config from environment variables

The agent must not hardcode any URLs, keys, or model names. It will read:

- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL`
- `LMS_API_KEY`
- `AGENT_API_BASE_URL` with default `http://localhost:42002`

For local convenience, the script will load values from:

- `.env.agent.secret`
- `.env.docker.secret`
- `.env`

### 3. Improve the system prompt

The prompt should explicitly tell the LLM which source of truth to use:

- `read_file` for wiki instructions, code, Docker files, and ETL logic
- `list_files` for structure discovery
- `query_api` for current runtime behavior, item counts, status codes, and reproducing API errors

For bug diagnosis, the prompt should encourage a two-step workflow:

1. reproduce the problem with `query_api`
2. inspect code with `read_file`

### 4. Harden the agent loop

I will fix a common failure mode where tool-calling responses have `content: null`. The loop will use:

```python
msg.get("content") or ""
```

I will also:

- keep a tool call log for debugging and eval checks
- infer `source` from the last file-based tool call
- truncate long tool outputs so the model does not loop on oversized files

### 5. Add regression tests

I will add 2 tool-selection tests:

- framework question → must use `read_file`
- item count question → must use `query_api`

To keep tests deterministic, they will use a stub LLM instead of a real network call.

## Initial benchmark diagnosis

I could not run `uv run run_eval.py` in this environment because the required local secrets and live services are not available here.

Expected first weak spots before the fix:

- no `query_api` tool at all
- `requests` and `python-dotenv` were imported even though they are not declared in project dependencies
- no clear distinction between wiki answers and runtime system answers
- fragile handling of `content: null`

## Iteration strategy

1. finish the tool implementation
2. verify tests locally
3. start `run_eval.py`
4. for each failed prompt, check whether the problem is:
   - wrong tool choice
   - unclear tool schema
   - wrong API path or params
   - weak system prompt
5. tighten the prompt and tool descriptions until all 10 local questions pass

## Local setup reminders for the lab

To reset the lab cleanly on your machine:

1. delete the old `se-toolkit-lab-6` folder
2. clone the fork again into `software-engineering-toolkit`
3. open the repo in `VS Code` from WSL
4. on the VM, start the Qwen/OpenAI-compatible API server
5. on WSL, point `.env.agent.secret` to `http://<vm-ip>:<qwen-port>/v1`
6. keep `.env.docker.secret` local for the backend key used by `query_api`
7. run the backend locally so the agent can query `http://localhost:42002`

That gives the intended architecture:

- WSL runs `agent.py`
- the agent sends LLM requests to the VM
- the local backend is queried through `query_api`
- the answer returns back to WSL
