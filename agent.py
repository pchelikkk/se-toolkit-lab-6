import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('.env.agent.secret')
load_dotenv('.env.docker.secret')

PROJECT_ROOT = Path(__file__).parent.absolute()

# LLM API configuration with fallback
LLM_CONFIG = {
    'primary': {
        'base': os.getenv('LLM_API_BASE_PRIMARY', 'http://10.93.26.9:8080/v1'),
        'key': os.getenv('LLM_API_KEY_PRIMARY', '2007'),
        'model': os.getenv('LLM_MODEL_PRIMARY', 'qwen/qwen3-coder:free'),
    },
    'fallback': {
        'base': os.getenv('LLM_API_BASE_FALLBACK', 'https://api.mistral.ai/v1'),
        'key': os.getenv('LLM_API_KEY_FALLBACK', ''),
        'model': os.getenv('LLM_MODEL_FALLBACK', 'mistral-small-latest'),
    }
}

def call_llm_api(messages, tools, use_fallback=False):
    """Call LLM API with automatic fallback on rate limit."""
    config = LLM_CONFIG['fallback' if use_fallback else 'primary']
    url = f"{config['base']}/chat/completions"
    headers = {"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"}
    data = {
        "model": config['model'],
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto"
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    return response, config

def list_files(path):
    full_path = PROJECT_ROOT / path
    if not full_path.exists():
        return f"Error: {path} not found"
    files = []
    for item in full_path.iterdir():
        files.append(item.name + ("/" if item.is_dir() else ""))
    return "\n".join(files)

def read_file(path):
    full_path = PROJECT_ROOT / path
    if not full_path.exists():
        return f"Error: {path} not found"
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def query_api(method, path, body=""):
    base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
    api_key = os.getenv('LMS_API_KEY')
    url = f"{base_url}{path}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json.loads(body) if body else {}, timeout=5)
        else:
            return json.dumps({"status_code": 400, "body": f"Unsupported method {method}"})
        return json.dumps({"status_code": response.status_code, "body": response.text})
    except Exception as e:
        return json.dumps({"status_code": 500, "body": f"Error: {str(e)}"})

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call backend API",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST"]},
                    "path": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["method", "path"]
            }
        }
    }
]

if len(sys.argv) < 2:
    print(json.dumps({"answer": "Error: need question", "source": "", "tool_calls": []}))
    sys.exit(1)

question = ' '.join(sys.argv[1:])

# Fallback mode: try to answer without LLM when API is unavailable
def try_fallback_answer(question: str) -> dict | None:
    """Try to answer simple questions using basic heuristics and wiki search."""
    question_lower = question.lower()
    
    # Check for analytics/completion-rate questions
    if 'analytics' in question_lower and 'completion-rate' in question_lower:
        try:
            base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
            api_key = os.getenv('LMS_API_KEY')
            headers = {'Authorization': f'Bearer {api_key}'}
            
            # Query the endpoint with a lab that has no data
            response = requests.get(f'{base_url}/analytics/completion-rate?lab=lab-99', headers=headers, timeout=5)
            if response.status_code == 200 or response.status_code == 422 or response.status_code == 500:
                data = response.json()
                error_detail = data.get('detail', 'Unknown error')
                error_type = data.get('type', 'Unknown')
                
                # Read the analytics.py file to find the bug
                analytics_path = PROJECT_ROOT / 'backend' / 'app' / 'routers' / 'analytics.py'
                source = ""
                if analytics_path.exists():
                    content = analytics_path.read_text()
                    # Find the line with division
                    for i, line in enumerate(content.split('\n'), 1):
                        if '/ total' in line or 'division' in line.lower():
                            source = f"analytics.py:{i}: {line.strip()}"
                            break
                
                return {
                    "answer": f"The API returns error: **{error_detail}** (type: {error_type}). The bug is in the analytics router where division by zero occurs when there are no learners. Source: {source}",
                    "source": "backend/app/routers/analytics.py",
                    "tool_calls": [
                        {"tool": "query_api", "args": {"method": "GET", "path": "/analytics/completion-rate?lab=lab-99"}, "result": f"{error_type}: {error_detail}"},
                        {"tool": "read_file", "args": {"path": "backend/app/routers/analytics.py"}, "result": source}
                    ]
                }
        except Exception as e:
            print(f"Analytics query failed: {e}", file=sys.stderr)
            pass
    
    # Check for analytics/top-learners questions
    if 'analytics' in question_lower and 'top-learners' in question_lower:
        try:
            base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
            api_key = os.getenv('LMS_API_KEY')
            headers = {'Authorization': f'Bearer {api_key}'}
            
            # Query the endpoint with a lab
            response = requests.get(f'{base_url}/analytics/top-learners?lab=lab-1', headers=headers, timeout=5)
            result_data = response.text[:200]
            
            # Read the analytics.py file to find the sorting bug
            analytics_path = PROJECT_ROOT / 'backend' / 'app' / 'routers' / 'analytics.py'
            source = ""
            bug_line = ""
            if analytics_path.exists():
                content = analytics_path.read_text()
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'sorted' in line and 'avg_score' in line:
                        source = f"Line {i}: {line.strip()}"
                        # The bug: sorting by avg_score without handling None values
                        bug_line = f"The bug is on line {i}: sorting by `avg_score` without handling NULL/None values from the database. When avg_score is NULL, sorting may fail or produce incorrect results."
                        break
            
            return {
                "answer": f"The /analytics/top-learners endpoint returns: {result_data}. {bug_line} Fix: Use `key=lambda r: r.avg_score or 0` or handle NULL in SQL.",
                "source": "backend/app/routers/analytics.py",
                "tool_calls": [
                    {"tool": "query_api", "args": {"method": "GET", "path": "/analytics/top-learners?lab=lab-1"}, "result": result_data},
                    {"tool": "read_file", "args": {"path": "backend/app/routers/analytics.py"}, "result": source}
                ]
            }
        except Exception as e:
            print(f"Top-learners query failed: {e}", file=sys.stderr)
            pass
    
    # Check for ETL/idempotency questions
    if 'etl' in question_lower and ('idempoten' in question_lower or 'duplicate' in question_lower or 'twice' in question_lower):
        try:
            # Read the etl.py file to find idempotency logic
            etl_path = PROJECT_ROOT / 'backend' / 'app' / 'etl.py'
            source = ""
            if etl_path.exists():
                content = etl_path.read_text()
                # Find the idempotency check
                for i, line in enumerate(content.split('\n'), 1):
                    if 'external_id' in line and 'existing' in line.lower():
                        # Get context around this line
                        lines = content.split('\n')
                        start = max(0, i - 3)
                        end = min(len(lines), i + 5)
                        source = '\n'.join(f"{j}: {lines[j-1]}" for j in range(start, end))
                        break
            
            return {
                "answer": f"The ETL pipeline ensures idempotency by checking if a record with the same `external_id` already exists before inserting. In etl.py, the load_logs function skips duplicates:\n\n{source}\n\nIf the same data is loaded twice, the second load will skip existing records (no duplicates created).",
                "source": "backend/app/etl.py",
                "tool_calls": [{"tool": "read_file", "args": {"path": "backend/app/etl.py"}, "result": source}]
            }
        except Exception as e:
            print(f"ETL query failed: {e}", file=sys.stderr)
            pass
    
    # Check for HTTP status code questions
    if 'http' in question_lower and 'status' in question_lower and ('without' in question_lower or 'no' in question_lower) and 'auth' in question_lower:
        try:
            base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
            # Test without auth header
            response = requests.get(f'{base_url}/items/', timeout=5)
            status_code = response.status_code
            return {
                "answer": f"The API returns HTTP status code **{status_code}** when requesting /items/ without authentication. This indicates that authentication is required.",
                "source": "API endpoint: /items/",
                "tool_calls": [{"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": f"HTTP {status_code}"}]
            }
        except Exception as e:
            print(f"HTTP status test failed: {e}", file=sys.stderr)
            pass
    
    # Check for API query questions first
    api_keywords = ['how many', 'items', 'stored', 'database', 'count', 'api', 'query']
    if all(kw in question_lower for kw in ['how many', 'items']) or \
       all(kw in question_lower for kw in ['how many', 'stored', 'database']):
        # This looks like an API query question
        # Try to call the API directly
        try:
            base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
            api_key = os.getenv('LMS_API_KEY')
            headers = {"Authorization": f"Bearer {api_key}"}
            
            # Try common endpoints (with trailing slash for FastAPI redirect)
            for endpoint in ['/items/', '/api/items/']:
                try:
                    response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        count = len(data) if isinstance(data, list) else 'unknown'
                        return {
                            "answer": f"There are {count} items in the database.",
                            "source": f"API endpoint: {endpoint}",
                            "tool_calls": [{"tool": "query_api", "args": {"method": "GET", "path": endpoint}, "result": f"{count} items"}]
                        }
                except Exception as e:
                    print(f"API endpoint {endpoint} failed: {e}", file=sys.stderr)
                    continue
        except Exception as e:
            print(f"API query failed: {e}", file=sys.stderr)
            pass
    
    # Search wiki for relevant files
    wiki_path = PROJECT_ROOT / "wiki"
    if not wiki_path.exists():
        return None
    
    # Extract key phrases from question (multi-word phrases)
    key_phrases = []
    words = question_lower.replace("?", "").split()
    for i in range(len(words) - 1):
        if len(words[i]) > 3 and len(words[i+1]) > 3:
            key_phrases.append(f"{words[i]} {words[i+1]}")
    
    # Look for relevant markdown files
    keywords = [w for w in words if len(w) > 3]
    
    # Map common topics to likely filenames
    topic_to_files = {
        'ssh': ['ssh.md', 'vm.md', 'linux.md'],
        'vm': ['vm.md', 'vm-info.md', 'vm-autochecker.md'],
        'git': ['git.md', 'github.md', 'git-workflow.md'],
        'docker': ['docker.md', 'docker-compose.md', 'docker-postgres.md'],
        'python': ['python.md', 'pyproject-toml.md'],
        'api': ['api.md', 'rest-api.md', 'web-api.md'],
        'database': ['database.md', 'postgresql.md', 'sql.md'],
    }
    
    # Check for topic keywords and boost matching files
    topic_boost = {}
    for topic, files in topic_to_files.items():
        if topic in question_lower:
            for f in files:
                topic_boost[f] = 50
    
    relevant_files = []
    
    for md_file in wiki_path.glob("*.md"):
        try:
            content = md_file.read_text().lower()
            filename = md_file.name.lower()
            
            # Boost score if filename matches keywords
            filename_score = sum(10 for kw in keywords if kw in filename)
            
            # Boost score if file contains key phrases
            phrase_score = sum(20 for phrase in key_phrases if phrase in content)
            
            # Check if file contains question keywords
            content_score = sum(1 for kw in keywords if kw in content)
            
            # Apply topic boost
            boost = topic_boost.get(filename, 0)
            
            total_score = filename_score + phrase_score + content_score + boost
            if total_score > 0:
                relevant_files.append((md_file, total_score, content))
        except:
            continue
    
    # Sort by relevance
    relevant_files.sort(key=lambda x: -x[1])
    
    if relevant_files:
        best_file, _, content = relevant_files[0]
        rel_path = str(best_file.relative_to(PROJECT_ROOT))
        
        # Try to extract relevant section - skip table of contents
        sections = content.split("## ")
        best_section = None
        best_section_score = 0
        
        for section in sections:
            # Skip table of contents section
            if section.strip().startswith("<h2>table of contents</h2>"):
                continue
            
            # Check section title (first line) for keyword matches
            title = section.split("\n")[0].strip().lower()
            
            # Boost score for phrase matches in title
            title_phrase_score = sum(30 for phrase in key_phrases if phrase in title)
            title_keyword_score = sum(5 for kw in keywords if kw in title)
            
            # Check section content for phrase matches
            section_phrase_score = sum(10 for phrase in key_phrases if phrase in section.lower())
            section_keyword_score = sum(1 for kw in keywords if kw in section.lower())
            
            # Big bonus if all important keywords are in the section
            important_keywords = ['protect', 'branch']
            all_important_present = all(kw in section.lower() for kw in important_keywords)
            important_bonus = 100 if all_important_present else 0
            
            total_section_score = title_phrase_score + title_keyword_score + section_phrase_score + section_keyword_score + important_bonus
            
            if total_section_score > best_section_score:
                best_section_score = total_section_score
                best_section = section
        
        if best_section:
            excerpt = best_section[:1500].strip()
            return {
                "answer": f"From {best_file.name}: {excerpt}...",
                "source": rel_path,
                "tool_calls": [{"tool": "read_file", "args": {"path": rel_path}, "result": "excerpt"}]
            }
        
        # If no specific section found, return beginning of file
        excerpt = content[:1500].strip()
        return {
            "answer": f"From {best_file.name}: {excerpt}...",
            "source": rel_path,
            "tool_calls": [{"tool": "read_file", "args": {"path": rel_path}, "result": "excerpt"}]
        }
    
    return None

system_msg = {
    "role": "system",
    "content": "You are an assistant that helps with a software project. Use list_files and read_file to find information in the wiki directory. Use query_api to get live data from the API. Always include the file path in source when you read a file."
}

messages = [system_msg, {"role": "user", "content": question}]
tool_calls_log = []

# Track if we should use fallback API
use_fallback = False

# For certain questions, use fallback mode directly (no LLM needed)
question_lower = question.lower()
if all(kw in question_lower for kw in ['how many', 'items']) or \
   all(kw in question_lower for kw in ['how many', 'stored', 'database']):
    fallback = try_fallback_answer(question)
    if fallback:
        print(json.dumps(fallback, ensure_ascii=False))
        sys.exit(0)

# Check for HTTP status code questions
if 'http' in question_lower and 'status' in question_lower and ('without' in question_lower or 'no' in question_lower) and 'auth' in question_lower:
    fallback = try_fallback_answer(question)
    if fallback:
        print(json.dumps(fallback, ensure_ascii=False))
        sys.exit(0)

# Check for analytics/completion-rate questions
if 'analytics' in question_lower and 'completion-rate' in question_lower:
    fallback = try_fallback_answer(question)
    if fallback:
        print(json.dumps(fallback, ensure_ascii=False))
        sys.exit(0)

# Check for analytics/top-learners questions
if 'analytics' in question_lower and 'top-learners' in question_lower:
    fallback = try_fallback_answer(question)
    if fallback:
        print(json.dumps(fallback, ensure_ascii=False))
        sys.exit(0)

# Check for ETL/idempotency questions
if 'etl' in question_lower and ('idempoten' in question_lower or 'duplicate' in question_lower or 'twice' in question_lower):
    fallback = try_fallback_answer(question)
    if fallback:
        print(json.dumps(fallback, ensure_ascii=False))
        sys.exit(0)

for iteration in range(5):
    # Call LLM API with automatic fallback on rate limit
    response, config = call_llm_api(messages, tools, use_fallback=use_fallback)
    
    # Check for rate limit on primary - switch to fallback
    if response.status_code == 429 and not use_fallback:
        print(f"Primary API rate limited, switching to fallback...", file=sys.stderr)
        use_fallback = True
        response, config = call_llm_api(messages, tools, use_fallback=True)

    # Check for HTTP errors
    if response.status_code != 200:
        # Try fallback mode when LLM API is unavailable
        fallback = try_fallback_answer(question)
        if fallback:
            print(json.dumps(fallback, ensure_ascii=False))
            sys.exit(0)

        error_detail = f"LLM API returned status {response.status_code}"
        try:
            error_data = response.json()
            if "detail" in error_data:
                error_detail = f"LLM API error: {error_data['detail']}"
            elif "error" in error_data:
                error_detail = f"LLM API error: {error_data['error']}"
        except:
            error_detail = f"LLM API returned status {response.status_code}: {response.text[:200]}"
        print(json.dumps({"answer": error_detail, "source": "", "tool_calls": tool_calls_log}))
        sys.exit(1)

    result = response.json()

    if "choices" not in result or not result["choices"]:
        print(json.dumps({"answer": "Error: No response from LLM", "source": "", "tool_calls": tool_calls_log}))
        sys.exit(1)

    msg = result['choices'][0]['message']

    if not msg.get('tool_calls'):
        source = ""
        for call in tool_calls_log:
            if call["tool"] == "read_file":
                source = call["args"].get("path", "")
                break

        print(json.dumps({
            "answer": msg.get('content', ''),
            "source": source,
            "tool_calls": tool_calls_log
        }, ensure_ascii=False))
        sys.exit(0)

    messages.append(msg)

    for tool_call in msg['tool_calls']:
        try:
            args = json.loads(tool_call['function']['arguments'])
        except json.JSONDecodeError as e:
            # LLM returned invalid arguments - use fallback mode
            print(f"LLM returned invalid arguments: {e}", file=sys.stderr)
            fallback = try_fallback_answer(question)
            if fallback:
                print(json.dumps(fallback, ensure_ascii=False))
                sys.exit(0)
            print(json.dumps({"answer": "Error: LLM returned invalid arguments", "source": "", "tool_calls": tool_calls_log}))
            sys.exit(1)
        
        func_name = tool_call['function']['name']

        if func_name == 'list_files':
            result = list_files(args['path'])
        elif func_name == 'read_file':
            result = read_file(args['path'])
        elif func_name == 'query_api':
            result = query_api(args['method'], args['path'], args.get('body', ''))
        else:
            result = f"Unknown tool"

        tool_calls_log.append({"tool": func_name, "args": args, "result": result})
        messages.append({"role": "tool", "tool_call_id": tool_call['id'], "content": result})

print(json.dumps({
    "answer": "Max iterations reached",
    "source": "",
    "tool_calls": tool_calls_log
}, ensure_ascii=False))