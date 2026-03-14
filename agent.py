import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv('.env.agent.secret')

if len(sys.argv) < 2:
    print("Error: need a question", file=sys.stderr)
    sys.exit(1)

question = ' '.join(sys.argv[1:])

api_key = os.getenv('LLM_API_KEY')
api_base = os.getenv('LLM_API_BASE')
model = os.getenv('LLM_MODEL')

if not api_key or not api_base:
    print("Error: missing API config in .env.agent.secret", file=sys.stderr)
    sys.exit(1)

url = f"{api_base}/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
data = {
    "model": model,
    "messages": [{"role": "user", "content": question}]
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    answer = result['choices'][0]['message']['content']
    print(json.dumps({"answer": answer, "tool_calls": []}))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
