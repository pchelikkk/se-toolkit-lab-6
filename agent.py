import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('.env.agent.secret')

PROJECT_ROOT = Path(__file__).parent.absolute()

def list_files(path):
    """Show files in a folder."""
    full_path = PROJECT_ROOT / path
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        return "Error: path outside project"
    if not full_path.exists():
        return "Error: path not found"
    if full_path.is_file():
        return "Error: path is a file, not folder"
    
    files = []
    for item in full_path.iterdir():
        if item.is_dir():
            files.append(item.name + "/")
        else:
            files.append(item.name)
    return "\n".join(files)

def read_file(path):
    """Read file contents."""
    full_path = PROJECT_ROOT / path
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        return "Error: path outside project"
    if not full_path.exists():
        return "Error: file not found"
    if not full_path.is_file():
        return "Error: not a file"
    
    with open(full_path, 'r', encoding='utf-8') as f:
        return f.read()

def call_llm(messages, tools=None):
    """Send request to LLM and return response."""
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL')
    
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": messages
    }
    if tools:
        data["tools"] = tools
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    return response.json()

if len(sys.argv) < 2:
    print("Error: need a question", file=sys.stderr)
    sys.exit(1)

question = ' '.join(sys.argv[1:])

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a folder",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    }
]

system_msg = {
    "role": "system",
    "content": "You are a documentation assistant. Use list_files and read_file to find answers in the wiki folder. Always include the source file in your answer like wiki/file.md#section."
}

messages = [system_msg, {"role": "user", "content": question}]
tool_calls_log = []
max_calls = 10

for _ in range(max_calls):
    result = call_llm(messages, tools)
    msg = result['choices'][0]['message']
    
    if not msg.get('tool_calls'):
        answer = msg['content']
        source = ""
        if "wiki/" in answer and ".md#" in answer:
            parts = answer.split()
            for part in parts:
                if "wiki/" in part and ".md#" in part:
                    source = part.strip('.,!?')
                    break
        
        output = {
            "answer": answer,
            "source": source,
            "tool_calls": tool_calls_log
        }
        print(json.dumps(output, ensure_ascii=False))
        sys.exit(0)
    
    messages.append(msg)
    for tool_call in msg['tool_calls']:
        func_name = tool_call['function']['name']
        args = json.loads(tool_call['function']['arguments'])
        
        if func_name == "list_files":
            result = list_files(args.get('path', ''))
        elif func_name == "read_file":
            result = read_file(args.get('path', ''))
        else:
            result = f"Error: unknown tool {func_name}"
        
        tool_calls_log.append({
            "tool": func_name,
            "args": args,
            "result": result
        })
        
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": result
        })

print(json.dumps({
    "answer": "Max tool calls reached",
    "source": "",
    "tool_calls": tool_calls_log
}, ensure_ascii=False))
