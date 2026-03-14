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
