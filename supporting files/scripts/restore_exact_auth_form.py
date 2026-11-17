import json

with open(r'C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    saved_l1 = None
    saved_mid = None
    saved_l2 = None
    for line in f:
        d = json.loads(line)
        c = str(d.get('content', ''))
        if 'Showing lines 1-150 of 285' in c and saved_l1 is None:
            part1 = c.split("Showing lines 1-150 of 285")[1].split("\n", 1)[1]
            saved_l1 = [l.split(": ", 1)[1] for l in part1.strip().split("\n") if ": " in l]
        if 'Showing lines 145-167 of 285' in c and saved_mid is None:
            partm = c.split("Showing lines 145-167 of 285")[1].split("\n", 1)[1]
            saved_mid = [l.split(": ", 1)[1] for l in partm.strip().split("\n") if ": " in l]
        if 'Showing lines 161-285 of 285' in c and saved_l2 is None:
            part2 = c.split("Showing lines 161-285 of 285")[1].split("\n", 1)[1]
            saved_l2 = [l.split(": ", 1)[1] for l in part2.strip().split("\n") if ": " in l]

print(f"L1 (1-150): {len(saved_l1)} lines")
print(f"Mid (145-167): {len(saved_mid)} lines")
print(f"L2 (161-285): {len(saved_l2)} lines")

# Assemble lines 1 to 285:
# saved_l1 has lines 1-144 (indices 0..143)
# saved_mid has lines 145-167 (indices 0..22)
# saved_l2 has lines 168-285 (indices 7..) since line 161-167 are indices 0-6 in saved_l2
full_code = saved_l1[:144] + saved_mid + saved_l2[7:]
print(f"Total lines assembled: {len(full_code)}")

with open(r'C:\yash\projects\pusher\frontend\src\components\auth\AuthFormPanel.jsx', 'w', encoding='utf-8') as out:
    out.write("\n".join(full_code) + "\n")

print("Successfully wrote exact 285 lines to AuthFormPanel.jsx!")
