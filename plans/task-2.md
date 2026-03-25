# Task 2 Plan

## Tools

- `list_files(path)` - shows contents of a folder
- `read_file(path)` - reads a file

## How it works

1. Send question + tool descriptions to LLM
2. If LLM wants to call a tool:
   - Run the tool
   - Send result back to LLM
   - Repeat (max 10 times)
3. If LLM gives answer - print JSON

## Security

- Check that files are inside project folder

## Output format

```json
{
  "answer": "text",
  "source": "path/to/file#section",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "files..."}
  ]
}
```
