import json

with open(r'C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        idx = d.get('step_index', 0)
        if 1448 <= idx <= 1515:
            tool_calls = d.get('tool_calls', [])
            tc_names = [tc.get('name') for tc in tool_calls] if tool_calls else []
            content = str(d.get('content', ''))
            print(f"STEP {idx} ({d.get('type')}, {d.get('source')}): tools={tc_names} content={content[:100]}")
