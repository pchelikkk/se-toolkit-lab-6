# Agent

## What it does
It takes a question and returns answer from LLM.

## Setup
1. Copy .env.agent.example to .env.agent.secret
2. Fill in:
   - LLM_API_KEY=key
   - LLM_API_BASE=http://10.93.26.9:11434/v1
   - LLM_MODEL=qwen3-coder-plus

## Usage
```bash
uv run agent.py "What is REST?"

## Tools
- `list_files(path)` - shows contents of a directory
- `read_file(path)` - reads file contents

## Agentic Loop
1. Send question + tool definitions to LLM
2. If LLM calls tools → execute them → feed results back
3. Repeat until answer (max 10 calls)
4. Output JSON with answer, source, and tool_calls log

## Task 3 - System Agent

### New tool: query_api
- Calls the backend API using LMS_API_KEY
- Supports GET and POST
- Base URL from AGENT_API_BASE_URL (default localhost:42002)

### How it decides
- Wiki questions → read_file on wiki/
- Code questions → read_file on backend/
- Data questions (counts, scores) → query_api
- Error debugging → query_api then read_file

### Environment
- LLM_API_KEY, LLM_API_BASE, LLM_MODEL: from .env.agent.secret
- LMS_API_KEY: from .env.docker.secret  
- AGENT_API_BASE_URL: optional, defaults to localhost

### Benchmark score
- Passed all 10 local questions
- Fixed: [список что чинили]
