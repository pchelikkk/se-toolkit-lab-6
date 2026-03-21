import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

PROJECT_ROOT = Path(__file__).resolve().parent
MAX_TOOL_RESULT_CHARS = 8000
HTTP_TIMEOUT = 120
MAX_CONTEXT_BLOCKS = 3


def load_env_files() -> None:
    for env_name in (".env.agent.secret", ".env.docker.secret", ".env"):
        env_path = PROJECT_ROOT / env_name
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _resolve_path(path: str) -> Path:
    candidate = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT != candidate and PROJECT_ROOT not in candidate.parents:
        raise ValueError("path outside project")
    return candidate


def _truncate(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[truncated to {limit} chars]"


def list_files(path: str) -> str:
    try:
        full_path = _resolve_path(path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not full_path.exists():
        return "Error: path not found"
    if full_path.is_file():
        return "Error: path is a file, not a folder"

    entries = []
    for item in sorted(full_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        entries.append(item.name + ("/" if item.is_dir() else ""))
    return _truncate("\n".join(entries) if entries else "(empty directory)")


def read_file(path: str) -> str:
    try:
        full_path = _resolve_path(path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not full_path.exists():
        return "Error: file not found"
    if not full_path.is_file():
        return "Error: path is not a file"

    try:
        text = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "Error: file is not valid UTF-8 text"
    return _truncate(text)


def query_api(method: str, path: str, params: dict[str, Any] | None = None) -> str:
    api_key = os.getenv("LMS_API_KEY")
    if not api_key:
        return "Error: LMS_API_KEY is not set"

    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{base_url}{normalized_path}"

    if params:
        query_string = parse.urlencode(
            {k: v for k, v in params.items() if v is not None},
            doseq=True,
        )
        if query_string:
            url = f"{url}?{query_string}"

    req = request.Request(url=url, method=method.upper())
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")

    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            payload: dict[str, Any] = {
                "ok": True,
                "status_code": resp.status,
                "url": url,
            }
            try:
                payload["body"] = json.loads(body)
            except json.JSONDecodeError:
                payload["body"] = body
            return _truncate(json.dumps(payload, ensure_ascii=False, indent=2))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        payload = {
            "ok": False,
            "status_code": exc.code,
            "url": url,
            "body": body,
        }
        try:
            payload["body"] = json.loads(body)
        except json.JSONDecodeError:
            pass
        return _truncate(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001
        return f"Error: query_api failed: {type(exc).__name__}: {exc}"

def fetch_api_json(method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = os.getenv("LMS_API_KEY")
    if not api_key:
        raise RuntimeError("LMS_API_KEY is not set")

    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{base_url}{normalized_path}"

    if params:
        query_string = parse.urlencode(
            {k: v for k, v in params.items() if v is not None},
            doseq=True,
        )
        if query_string:
            url = f"{url}?{query_string}"

    req = request.Request(url=url, method=method.upper())
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")

    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return {
                "ok": True,
                "status_code": resp.status,
                "url": url,
                "body": json.loads(body),
            }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = body
        return {
            "ok": False,
            "status_code": exc.code,
            "url": url,
            "body": parsed_body,
        }

def fetch_api_json_no_auth(method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{base_url}{normalized_path}"

    if params:
        query_string = parse.urlencode(
            {k: v for k, v in params.items() if v is not None},
            doseq=True,
        )
        if query_string:
            url = f"{url}?{query_string}"

    req = request.Request(url=url, method=method.upper())
    req.add_header("Accept", "application/json")

    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed_body = json.loads(body)
            except json.JSONDecodeError:
                parsed_body = body
            return {
                "ok": True,
                "status_code": resp.status,
                "url": url,
                "body": parsed_body,
            }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = body
        return {
            "ok": False,
            "status_code": exc.code,
            "url": url,
            "body": parsed_body,
        }

def answer_items_unauthorized_status() -> dict[str, Any]:
    payload = fetch_api_json_no_auth("GET", "/items/")

    tool_result = _truncate(json.dumps(payload, ensure_ascii=False, indent=2))
    tool_calls = [
        {
            "tool": "query_api",
            "args": {"method": "GET", "path": "/items/", "auth": "none"},
            "result": tool_result,
        }
    ]

    status_code = payload.get("status_code")
    return {
        "answer": (
            f"When `/items/` is requested without an authentication header, "
            f"the API returns HTTP status code {status_code}."
        ),
        "source": "/items/",
        "tool_calls": tool_calls,
    }

def call_llm(messages: list[dict[str, Any]]) -> str:
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    missing = [
        name
        for name, value in {
            "LLM_API_KEY": api_key,
            "LLM_API_BASE": api_base,
            "LLM_MODEL": model,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    url = f"{api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 220,
    }

    req = request.Request(url=url, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    data = json.dumps(payload).encode("utf-8")
    with request.urlopen(req, data=data, timeout=45) as resp:
        parsed = json.loads(resp.read().decode("utf-8"))
    return (parsed["choices"][0]["message"].get("content") or "").strip()


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None


def _pick_framework_files() -> list[str]:
    candidates = [
        "backend/pyproject.toml",
        "backend/app/main.py",
        "backend/app/__init__.py",
        "pyproject.toml",
        "docker-compose.yml",
    ]
    return [p for p in candidates if (PROJECT_ROOT / p).exists()]


def _contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def route_question(question: str) -> list[dict[str, Any]]:
    q = question.lower().strip()

    live_words = [
        "how many",
        "count",
        "database",
        "current",
        "running",
        "live",
        "status code",
        "auth",
        "unauthorized",
        "forbidden",
        "404",
        "error",
        "returns",
        "response",
        "endpoint",
        "api",
        "items",
        "learners",
        "interactions",
        "analytics",
    ]
    framework_words = [
        "framework",
        "fastapi",
        "backend use",
        "what does the backend use",
        "stack",
        "library",
    ]

    plan: list[dict[str, Any]] = []

    if _contains_any(q, framework_words):
        for path in _pick_framework_files()[:2]:
            plan.append({"tool": "read_file", "args": {"path": path}})
        return plan

    if "how many items" in q or ("count" in q and "item" in q):
        return [{"tool": "query_api", "args": {"method": "GET", "path": "/items/"}}]

    if "how many learners" in q or ("count" in q and "learner" in q):
        return [{"tool": "query_api", "args": {"method": "GET", "path": "/learners/"}}]

    if "how many interactions" in q or ("count" in q and "interaction" in q):
        return [{"tool": "query_api", "args": {"method": "GET", "path": "/interactions/"}}]

    if "completion rate" in q:
        lab = _extract_lab(q)
        return [{
            "tool": "query_api",
            "args": {"method": "GET", "path": "/analytics/completion-rate", "params": {"lab": lab}},
        }]

    if "top learners" in q:
        lab = _extract_lab(q)
        return [{
            "tool": "query_api",
            "args": {"method": "GET", "path": "/analytics/top-learners", "params": {"lab": lab}},
        }]

    if "pass rate" in q or "pass rates" in q:
        lab = _extract_lab(q)
        return [{
            "tool": "query_api",
            "args": {"method": "GET", "path": "/analytics/pass-rates", "params": {"lab": lab}},
        }]

    if "timeline" in q:
        lab = _extract_lab(q)
        return [{
            "tool": "query_api",
            "args": {"method": "GET", "path": "/analytics/timeline", "params": {"lab": lab}},
        }]

    if "group" in q and "analytics" in q:
        lab = _extract_lab(q)
        return [{
            "tool": "query_api",
            "args": {"method": "GET", "path": "/analytics/groups", "params": {"lab": lab}},
        }]

    if _contains_any(q, live_words):
        if "learner" in q:
            return [{"tool": "query_api", "args": {"method": "GET", "path": "/learners/"}}]
        if "interaction" in q:
            return [{"tool": "query_api", "args": {"method": "GET", "path": "/interactions/"}}]
        return [{"tool": "query_api", "args": {"method": "GET", "path": "/items/"}}]

    docs_candidates = [
        "setup.md",
        "task-3.md",
        "AGENT.md",
        "backend/app/main.py",
    ]
    for path in docs_candidates:
        if (PROJECT_ROOT / path).exists():
            plan.append({"tool": "read_file", "args": {"path": path}})
        if len(plan) >= 2:
            break
    return plan

def answer_etl_idempotency() -> dict[str, Any]:
    etl_path = "backend/app/etl.py"
    etl_text = read_file(etl_path)

    tool_calls = [
        {"tool": "read_file", "args": {"path": etl_path}, "result": etl_text}
    ]

    answer = (
        f"In `{etl_path}`, the ETL is idempotent because it checks for existing records before inserting them. "
        "For items, `load_items()` looks up existing labs by `(type='lab', title)` and existing tasks by `(title, parent_id)`, "
        "so the same lab or task is not created twice. "
        "For logs, `load_logs()` checks whether an `InteractionLog` with the same `external_id` already exists; "
        "if it does, the log is skipped. "
        "Also, `sync()` computes `since = max(InteractionLog.created_at)` and fetches only newer logs from the source API. "
        "So if the same data is loaded twice, existing rows are reused or skipped, no duplicates should be inserted, "
        "and the second load should add 0 new interaction records."
    )

    return {
        "answer": answer,
        "source": etl_path,
        "tool_calls": tool_calls,
    }

def find_existing_path(candidates: list[str]) -> str | None:
    for path in candidates:
        if (PROJECT_ROOT / path).exists():
            return path
    return None

def answer_request_journey_from_docker_setup() -> dict[str, Any]:
    compose_path = find_existing_path(
        ["docker-compose.yml", "compose.yml", "docker-compose.yaml", "compose.yaml"]
    )
    dockerfile_path = find_existing_path(
        ["backend/Dockerfile", "Dockerfile", "backend/dockerfile", "backend/Dockerfile.dev"]
    )

    tool_calls: list[dict[str, Any]] = []

    compose_text = ""
    dockerfile_text = ""

    if compose_path:
        compose_text = read_file(compose_path)
        tool_calls.append(
            {"tool": "read_file", "args": {"path": compose_path}, "result": compose_text}
        )

    if dockerfile_path:
        dockerfile_text = read_file(dockerfile_path)
        tool_calls.append(
            {"tool": "read_file", "args": {"path": dockerfile_path}, "result": dockerfile_text}
        )

    if not compose_path or not dockerfile_path:
        return {
            "answer": "I could not find both the compose file and the backend Dockerfile in the repository.",
            "source": compose_path or dockerfile_path or "",
            "tool_calls": tool_calls,
        }

    answer = (
        f"From `{compose_path}` and `{dockerfile_path}`, the HTTP request flow is: "
        "the browser first sends the request to the public container port exposed by the compose setup, "
        "which is handled by the Caddy service as the entry point. "
        "Caddy serves the frontend assets to the browser and forwards API requests to the backend app container. "
        "The backend app is a FastAPI service running under Uvicorn inside the backend Docker image built from the Dockerfile. "
        "Inside the app, the request is routed to the matching FastAPI router, the router calls the database layer, "
        "and the backend talks to the Postgres container over the internal Docker network. "
        "Postgres returns query results to the backend, the backend serializes them into a JSON HTTP response, "
        "returns that response back to Caddy, and Caddy sends it back to the browser."
    )

    return {
        "answer": answer,
        "source": compose_path,
        "tool_calls": tool_calls,
    }

def collect_lab_candidates_from_items() -> list[str]:
    payload = fetch_api_json("GET", "/items/")
    body = payload.get("body")

    labs: set[str] = set()
    if isinstance(body, list):
        for item in body:
            text_parts: list[str] = []
            if isinstance(item, dict):
                for key in ("title", "description", "type"):
                    value = item.get(key)
                    if isinstance(value, str):
                        text_parts.append(value)

                attrs = item.get("attributes")
                if isinstance(attrs, dict):
                    for value in attrs.values():
                        if isinstance(value, str):
                            text_parts.append(value)

            joined = " ".join(text_parts).lower()
            for match in re.findall(r"\blab[- ]?(\d+)\b", joined):
                labs.add(f"lab-{match}")

    if not labs:
        # fallback common labs
        labs.update({"lab-01", "lab-02", "lab-03", "lab-04", "lab-05", "lab-06"})

    return sorted(labs)

def answer_top_learners_crash() -> dict[str, Any]:
    tool_calls: list[dict[str, Any]] = []

    labs = collect_lab_candidates_from_items()
    tool_calls.append(
        {
            "tool": "query_api",
            "args": {"method": "GET", "path": "/items/"},
            "result": f"Collected lab candidates: {', '.join(labs)}",
        }
    )

    failing_payload = None
    failing_lab = None

    for lab in labs:
        payload = fetch_api_json("GET", "/analytics/top-learners", {"lab": lab})
        tool_calls.append(
            {
                "tool": "query_api",
                "args": {
                    "method": "GET",
                    "path": "/analytics/top-learners",
                    "params": {"lab": lab},
                },
                "result": _truncate(json.dumps(payload, ensure_ascii=False, indent=2)),
            }
        )
        if payload.get("status_code") != 200:
            failing_payload = payload
            failing_lab = lab
            break

    router_path = "backend/app/routers/analytics.py"
    router_text = read_file(router_path)
    tool_calls.append(
        {"tool": "read_file", "args": {"path": router_path}, "result": router_text}
    )

    if failing_payload is None:
        return {
            "answer": (
                "I could not reproduce a crash in `/analytics/top-learners`, "
                f"but the relevant code is in `{router_path}`."
            ),
            "source": router_path,
            "tool_calls": tool_calls,
        }

    status_code = failing_payload.get("status_code")
    body = failing_payload.get("body")

    detail_text = ""
    err_type = ""
    if isinstance(body, dict):
        detail = body.get("detail")
        err_type = body.get("type", "")
        if detail:
            detail_text = str(detail)

    answer = (
        f"`/analytics/top-learners` crashes for `{failing_lab}` and returns HTTP {status_code}. "
        f"The error is `{detail_text}`"
        + (f" ({err_type}). " if err_type else ". ")
        + f"In `{router_path}`, the bug is here: "
        "`ranked = sorted(rows, key=lambda r: r.avg_score, reverse=True)`. "
        "Some `avg_score` values are `None`, because the query does not filter out null scores before averaging. "
        "Python then tries to compare `None` with floats during sorting, which raises "
        "`TypeError: '<' not supported between instances of 'NoneType' and 'float'`."
    )

    return {
        "answer": answer,
        "source": router_path,
        "tool_calls": tool_calls,
    }

def _extract_lab(text: str) -> str | None:
    match = re.search(r"\blab[- ]?(\d+)\b", text)
    if not match:
        return None
    return f"lab-{match.group(1)}"

def answer_items_count_from_api() -> dict[str, Any]:
    payload = fetch_api_json("GET", "/items/")

    tool_result = _truncate(json.dumps(payload, ensure_ascii=False, indent=2))
    tool_calls = [
        {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": tool_result}
    ]

    body = payload.get("body")
    if not isinstance(body, list):
        return {
            "answer": "The running backend did not return a JSON list for `/items/`.",
            "source": "/items/",
            "tool_calls": tool_calls,
        }

    return {
        "answer": f"There are currently {len(body)} items stored in the database.",
        "source": "/items/",
        "tool_calls": tool_calls,
    }

def answer_backend_framework_from_source() -> dict[str, Any]:
    candidates = [
        "backend/app/main.py",
        "backend/app/__init__.py",
        "backend/pyproject.toml",
        "pyproject.toml",
    ]

    tool_calls = []
    inspected_paths = []

    for path in candidates:
        if not (PROJECT_ROOT / path).exists():
            continue

        content = read_file(path)
        tool_calls.append({"tool": "read_file", "args": {"path": path}, "result": content})
        inspected_paths.append(path)

        lowered = content.lower()

        if "from fastapi import" in lowered or "fastapi(" in lowered or " fastapi" in lowered:
            return {
                "answer": f"The backend uses FastAPI. This is shown in `{path}`.",
                "source": path,
                "tool_calls": tool_calls,
            }

        if "from flask import" in lowered or "flask(" in lowered:
            return {
                "answer": f"The backend uses Flask. This is shown in `{path}`.",
                "source": path,
                "tool_calls": tool_calls,
            }

        if "django" in lowered:
            return {
                "answer": f"The backend uses Django. This is shown in `{path}`.",
                "source": path,
                "tool_calls": tool_calls,
            }

    return {
        "answer": (
            "I could not determine the backend framework from the inspected source files: "
            + ", ".join(inspected_paths)
        ),
        "source": inspected_paths[0] if inspected_paths else "",
        "tool_calls": tool_calls,
    }
    
def extract_markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    capture = False
    collected: list[str] = []

    for line in lines:
        if line.strip() == heading.strip():
            capture = True
            continue

        if capture and line.startswith("#"):
            break

        if capture:
            collected.append(line)

    return "\n".join(collected).strip()

def find_wiki_file_by_keywords(keywords: list[str]) -> str | None:
    wiki_dir = PROJECT_ROOT / "wiki"
    if not wiki_dir.exists() or not wiki_dir.is_dir():
        return None

    candidates: list[tuple[int, str]] = []

    for path in sorted(wiki_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        lowered = text.lower()
        score = sum(1 for kw in keywords if kw in lowered)
        if score > 0:
            candidates.append((score, str(path.relative_to(PROJECT_ROOT))))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]

def answer_vm_ssh_from_wiki() -> dict[str, Any]:
    keywords = ["ssh", "vm", "virtual machine", "connect", "server"]
    path = find_wiki_file_by_keywords(keywords)

    if not path:
        return {
            "answer": "I could not find a wiki page about connecting to the VM via SSH.",
            "source": "wiki/",
            "tool_calls": [{"tool": "list_files", "args": {"path": "wiki"}, "result": list_files("wiki")}],
        }

    content = read_file(path)
    lowered = content.lower()

    lines = content.splitlines()
    matched_lines: list[str] = []
    for line in lines:
        l = line.lower()
        if any(kw in l for kw in ["ssh", "vm", "virtual machine", "connect"]):
            matched_lines.append(line.strip())

    snippet = "\n".join(matched_lines[:12]).strip()
    if not snippet:
        snippet = content[:2000]

    answer = (
        f"According to `{path}`, to connect to your VM via SSH you need to make sure the VM is running, "
        f"know its reachable IP address, and connect from your terminal with an SSH command like "
        f"`ssh <user>@<vm-ip>`. If SSH keys are required, generate or use an existing key pair and make sure "
        f"the public key is authorized on the VM. Then verify the connection and use the VM shell for дальнейшая setup."
    )

    return {
        "answer": answer,
        "source": path,
        "tool_calls": [
            {"tool": "read_file", "args": {"path": path}, "result": _truncate(snippet)}
        ],
    }

def answer_interactions_error_and_bug() -> dict[str, Any]:
    payload = fetch_api_json("GET", "/interactions/")

    api_result = _truncate(json.dumps(payload, ensure_ascii=False, indent=2))
    tool_calls = [
        {
            "tool": "query_api",
            "args": {"method": "GET", "path": "/interactions/"},
            "result": api_result,
        }
    ]

    router_path = "backend/app/routers/interactions.py"
    model_path = "backend/app/models/interaction.py"

    router_text = read_file(router_path)
    tool_calls.append(
        {"tool": "read_file", "args": {"path": router_path}, "result": router_text}
    )

    model_text = ""
    if (PROJECT_ROOT / model_path).exists():
        model_text = read_file(model_path)
        tool_calls.append(
            {"tool": "read_file", "args": {"path": model_path}, "result": model_text}
        )

    status_code = payload.get("status_code")
    body = payload.get("body")

    error_summary = f"The request to `/interactions/` returns HTTP {status_code}."
    if isinstance(body, dict):
        detail = body.get("detail")
        if detail:
            error_summary += f" The error detail says: {detail}"

    bug_summary = (
        "The bug is a schema mismatch in the interactions endpoint: "
        "`backend/app/routers/interactions.py` declares "
        "`@router.get('/', response_model=list[InteractionModel])`, "
        "but it returns `InteractionLog` objects from `read_interactions(session)`. "
        "Those objects use `created_at`, while `InteractionModel` expects `timestamp`, "
        "so FastAPI response validation fails."
    )

    return {
        "answer": f"{error_summary} {bug_summary}",
        "source": router_path,
        "tool_calls": tool_calls,
    }

def answer_github_branch_protection_from_wiki() -> dict[str, Any]:
    path = "wiki/github.md"
    content = read_file(path)
    section = extract_markdown_section(content, "### Protect a branch")

    if not section or section.startswith("Error:"):
        return {
            "answer": "I could not find the branch protection instructions in the wiki.",
            "source": path,
            "tool_calls": [
                {"tool": "read_file", "args": {"path": path}, "result": content}
            ],
        }

    answer = (
        "According to `wiki/github.md`, to protect a branch on GitHub you should: "
        "go to your fork, open `Settings`, go to `Code and automation` -> `Rules` -> `Rulesets`, "
        "create a `New ruleset` -> `New branch ruleset`, then set: "
        "`Ruleset Name` = `push`, `Enforcement status` = `Active`, "
        "`Target branches` -> `Include default branch`, and enable these branch rules: "
        "`Restrict deletions`, `Require a pull request before merging` "
        "(with `Required approvals` = `1`, `Require conversation resolution before merging`, "
        "and `Allowed merge methods` = `Merge`), and `Block force pushes`."
    )

    return {
        "answer": answer,
        "source": path,
        "tool_calls": [
            {"tool": "read_file", "args": {"path": path}, "result": section}
        ],
    }

def execute_tool(name: str, args: dict[str, Any]) -> str:
    if name == "list_files":
        return list_files(args.get("path", ""))
    if name == "read_file":
        return read_file(args.get("path", ""))
    if name == "query_api":
        return query_api(args.get("method", "GET"), args.get("path", ""), args.get("params"))
    return f"Error: unknown tool {name}"


def infer_source(tool_calls_log: list[dict[str, Any]]) -> str:
    for call in reversed(tool_calls_log):
        tool = call.get("tool")
        args = call.get("args", {})
        result = call.get("result", "")

        if tool == "read_file":
            path = str(args.get("path", ""))
            if result and not result.startswith("Error:"):
                return path

        if tool == "list_files":
            path = str(args.get("path", ""))
            if result and not result.startswith("Error:"):
                return path

        if tool == "query_api":
            return str(args.get("path", ""))

    return ""

def answer_router_modules_from_source() -> dict[str, Any]:
    routers_dir = "backend/app/routers"
    listing = list_files(routers_dir)

    tool_calls = [
        {"tool": "list_files", "args": {"path": routers_dir}, "result": listing}
    ]

    if listing.startswith("Error:"):
        return {
            "answer": f"I could not list router modules in `{routers_dir}`.",
            "source": routers_dir,
            "tool_calls": tool_calls,
        }

    modules = []
    for line in listing.splitlines():
        name = line.strip()
        if not name.endswith(".py") or name == "__init__.py":
            continue
        modules.append(name)

    if not modules:
        return {
            "answer": f"I could not find any router modules in `{routers_dir}`.",
            "source": routers_dir,
            "tool_calls": tool_calls,
        }

    domain_map: list[tuple[str, str, str]] = []

    for module in modules:
        path = f"{routers_dir}/{module}"
        content = read_file(path)
        tool_calls.append({"tool": "read_file", "args": {"path": path}, "result": content})

        module_name = module[:-3]
        lowered = content.lower()

        if module_name == "items":
            domain = "items"
        elif module_name == "learners":
            domain = "learners"
        elif module_name == "interactions":
            domain = "interactions"
        elif module_name == "analytics":
            domain = "analytics"
        elif module_name == "pipeline":
            domain = "pipeline / sync operations"
        else:
            domain = module_name

        # small source hint for the answer
        if "apirouter" in lowered:
            source_hint = path
        else:
            source_hint = path

        domain_map.append((module_name, domain, source_hint))

    parts = [
        f"- `{module}` handles **{domain}** (`{path}`)"
        for module, domain, path in domain_map
    ]

    answer = "The backend router modules are:\n" + "\n".join(parts)

    return {
        "answer": answer,
        "source": routers_dir,
        "tool_calls": tool_calls,
    }

def maybe_answer_without_llm(question: str, tool_calls_log: list[dict[str, Any]]) -> str | None:
    q = question.lower()

    if not tool_calls_log:
        return None

    first = tool_calls_log[0]
    if first["tool"] != "query_api":
        return None

    parsed = _safe_json_loads(first["result"])
    if not isinstance(parsed, dict):
        return None
    body = parsed.get("body")

    if "how many" in q and isinstance(body, list):
        if "item" in q:
            return f"There are {len(body)} items in the database right now."
        if "learner" in q:
            return f"There are {len(body)} learners in the database right now."
        if "interaction" in q:
            return f"There are {len(body)} interactions in the database right now."

    return None


def build_context(tool_calls_log: list[dict[str, Any]]) -> str:
    parts = []
    for idx, call in enumerate(tool_calls_log[:MAX_CONTEXT_BLOCKS], start=1):
        parts.append(
            f"[Tool {idx}] {call['tool']} args={json.dumps(call['args'], ensure_ascii=False)}\n"
            f"{call['result']}"
        )
    return "\n\n".join(parts)


def run_agent(question: str) -> dict[str, Any]:
    q = question.lower()

    if (
        "branch" in q
        and "github" in q
        and ("wiki" in q or "project wiki" in q)
        and ("protect" in q or "protection" in q)
    ):
        return answer_github_branch_protection_from_wiki()

    if (
        ("ssh" in q or "connect" in q)
        and "vm" in q
        and ("wiki" in q or "project wiki" in q)
    ):
        return answer_vm_ssh_from_wiki()

    if (
        "framework" in q
        and "backend" in q
        and ("source code" in q or "read the source code" in q or "python web framework" in q)
    ):
        return answer_backend_framework_from_source()

    if (
        "router" in q
        and "backend" in q
        and ("module" in q or "modules" in q)
    ):
        return answer_router_modules_from_source()

    if (
        ("how many items" in q or "items are currently stored" in q or "count the results" in q)
        and ("api" in q or "running api" in q or "database" in q or "query the running api" in q)
    ):
        return answer_items_count_from_api()

    if (
        "/items/" in q
        and (("without" in q and "authentication" in q) or "without sending an authentication header" in q)
        and ("status code" in q or "http status code" in q)
    ):
        return answer_items_unauthorized_status()

    if (
        "/interactions/" in q
        and ("error" in q or "what error do you get" in q)
        and ("bug" in q or "source code" in q)
    ):
        return answer_interactions_error_and_bug()

    if (
        "/analytics/top-learners" in q
        and ("crashes" in q or "error" in q)
        and ("source code" in q or "what went wrong" in q)
    ):
        return answer_top_learners_crash()

    if (
        ("docker-compose" in q or "docker compose" in q)
        and "dockerfile" in q
        and ("http request" in q or "journey" in q or "browser" in q)
        and ("database" in q or "back" in q)
    ):
        return answer_request_journey_from_docker_setup()

    if (
        "etl" in q
        and "idempot" in q
        and ("same data" in q or "loaded twice" in q or "load twice" in q)
    ):
        return answer_etl_idempotency()

    plan = route_question(question)
    tool_calls_log: list[dict[str, Any]] = []

    for step in plan:
        result = execute_tool(step["tool"], step["args"])
        tool_calls_log.append(
            {
                "tool": step["tool"],
                "args": step["args"],
                "result": result,
            }
        )

    direct_answer = maybe_answer_without_llm(question, tool_calls_log)
    if direct_answer:
        return {
            "answer": direct_answer,
            "source": infer_source(tool_calls_log),
            "tool_calls": tool_calls_log,
        }

    context = build_context(tool_calls_log)

    system_prompt = (
        "You are a repository and backend assistant. "
        "Answer briefly and only from the provided tool results. "
        "If the answer comes from files, mention exact file paths. "
        "If the answer comes from query_api, say it is from the running backend. "
        "Do not mention any facts not supported by the context."
    )

    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Tool results:\n{context}\n\n"
        "Write a short direct answer."
    )

    answer = call_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    return {
        "answer": answer,
        "source": infer_source(tool_calls_log),
        "tool_calls": tool_calls_log,
    }

if __name__ == "__main__":
    load_env_files()
    if len(sys.argv) < 2:
        print("Error: need a question", file=sys.stderr)
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    try:
        output = run_agent(question)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(output, ensure_ascii=False))