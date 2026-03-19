# Task 3 Plan: System Agent

## Goal

Add `query_api` tool to agent.py so it can query the running backend API and answer data-driven questions.

## What's new compared to Task 2

- New tool: `query_api(method, path, body)` that calls the backend API
- Backend authentication using `LMS_API_KEY` from `.env.docker.secret`
- Base URL from `AGENT_API_BASE_URL` environment variable (default: `http://localhost:42002`)
- Fallback mechanism for LLM rate limiting

## Implementation Plan

### Step 1: Add query_api function

```python
def query_api(method, path, body=""):
    base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
    api_key = os.getenv('LMS_API_KEY')
    # Make HTTP request with authentication
    # Return JSON with status_code and body
```

### Step 2: Register tool in tools list

Add tool definition with:

- name: `query_api`
- parameters: `method` (GET/POST), `path`, `body` (optional)

### Step 3: Handle tool execution in main loop

```python
if func_name == 'query_api':
    result = query_api(args['method'], args['path'], args.get('body', ''))
```

### Step 4: Environment setup

- `.env.agent.secret`: LLM credentials + `AGENT_API_BASE_URL` + `LMS_API_KEY`
- `.env.docker.secret`: `LMS_API_KEY` for backend auth

## How the agent decides which tool to use

| Question type | Tool | Example |
|--------------|------|---------|
| Wiki lookup | `read_file` | "What is GitHub?" |
| Code analysis | `read_file` | "What framework does backend use?" |
| Data query | `query_api` | "How many items in database?" |
| Error debugging | `query_api` + `read_file` | "What error does /analytics return?" |
| Directory listing | `list_files` | "What files are in wiki/?" |

## Fallback mechanism

To handle LLM rate limiting:

1. **Primary**: VM proxy (`http://10.93.26.9:8080/v1`) with free OpenRouter models
2. **Fallback**: Mistral AI API when primary returns 429
3. **Direct fallback**: For known patterns (API counts, HTTP status, analytics errors), bypass LLM entirely

## Testing strategy

1. Run `uv run run_eval.py` to test all 10 questions
2. Fix failing questions one by one
3. Target: 10/10 local questions passing

## Known issues to fix

- API endpoints need trailing slash (`/items/` not `/items`)
- Empty database returns 0 items (need at least 1 for tests)
- Analytics endpoints have bugs (division by zero, sorting issues)
- ETL pipeline uses `external_id` for idempotency

## Acceptance criteria

- [ ] `query_api` tool implemented and working
- [ ] `AGENT.md` updated with architecture (200+ words)
- [ ] `plans/task-3.md` exists with implementation plan
- [ ] All 10 local questions pass (10/10)
- [ ] Agent handles wiki, code, API, and debugging questions
