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
