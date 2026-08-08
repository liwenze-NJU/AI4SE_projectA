"""Manual DeepSeek API connectivity test.

NOT in CI, NOT auto-run, NOT in pytest. Requires a valid DEEPSEEK_API_KEY
environment variable. Does NOT accept command-line arguments for the key.

Usage:
    set DEEPSEEK_API_KEY=sk-...
    python scripts/deepseek_smoke_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeguard.llm.deepseek import DeepSeekAdapter


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("SKIP: DEEPSEEK_API_KEY environment variable not set")
        print("Set it via: set DEEPSEEK_API_KEY=sk-... (Windows)")
        return

    adapter = DeepSeekAdapter(api_key=api_key)
    print("Sending test request to DeepSeek API...")
    try:
        response = adapter.generate(
            session_id="smoke-test",
            context='Say "hello" and respond with {"action": "complete", "summary": "hello world"}',
        )
        print(f"  Model:      {response.model}")
        print(f"  Finish:     {response.finish_reason}")
        print(f"  Content:    {response.content[:100]}")
        print(f"  Tokens:     {response.token_used}")
        print(f"  Cost:       ${response.cost_used:.6f}")
        print("PASS: DeepSeek API connectivity verified")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()