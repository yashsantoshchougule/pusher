import json

with open(r'C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    saved_l1 = None
    saved_l2 = None
    for line in f:
        d = json.loads(line)
        c = str(d.get('content', ''))
        if 'Showing lines 1-150 of 285' in c and saved_l1 is None:
            part1 = c.split("Showing lines 1-150 of 285")[1].split("\n", 1)[1]
            saved_l1 = [l.split(": ", 1)[1] for l in part1.strip().split("\n") if ": " in l]
        if 'Showing lines 161-285 of 285' in c and saved_l2 is None:
            part2 = c.split("Showing lines 161-285 of 285")[1].split("\n", 1)[1]
            saved_l2 = [l.split(": ", 1)[1] for l in part2.strip().split("\n") if ": " in l]

print(f"L1: {len(saved_l1)}, L2: {len(saved_l2)}")

bridge = [
    '                  ? \'bg-[#455230] text-[#EBEBD8] shadow-sm\'',
    '                  : \'bg-[#EBEBD8]\'',
    '                  }`}',
    '              >',
    '                {agreedToTerms && <Check className="w-3.5 h-3.5 stroke-[3]" />}',
    '              </div>',
    '              <span>',
    '                I agree to the{\' \'}'
]

full_lines = saved_l1[:151] + bridge + saved_l2[0:]
print(f"Total lines: {len(full_lines)}")

with open(r'C:\yash\projects\pusher\frontend\src\components\auth\AuthFormPanel.jsx', 'w', encoding='utf-8') as f:
    f.write("\n".join(full_lines) + "\n")

print("AuthFormPanel.jsx restored successfully!")
