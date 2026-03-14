import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_agent():
    result = subprocess.run(
        [sys.executable, "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "answer" in output
    assert "tool_calls" in output
    assert isinstance(output["tool_calls"], list)

def test_agent_tool_list_files():
    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki directory?"],
        capture_output=True,
        text=True,
        timeout=60
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "tool_calls" in output
    assert any(call["tool"] == "list_files" for call in output["tool_calls"])

def test_agent_tool_read_file():
    result = subprocess.run(
        [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=60
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "tool_calls" in output
    assert any(call["tool"] == "read_file" for call in output["tool_calls"])
    assert "source" in output
