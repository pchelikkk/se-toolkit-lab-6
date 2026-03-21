# Task 1 Plan

## LLM Setup

- LLM: Qwen on VM (`http://10.93.26.9:11434/v1`)
- Model: qwen3-coder-plus
- API key from .env.agent.secret

## How it works

1. Read question from command line
2. Load config from .env.agent.secret
3. Send request to Qwen API on VM
4. Parse JSON response
5. Print result in expecting format

## Files

- agent.py - main code
- AGENT.md - short docs
- tests/test_agent.py - one test

## Test

- uv run agent.py "question" => should return JSON
- pytest should pass
