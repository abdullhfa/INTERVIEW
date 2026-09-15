import json
from collections import Counter
from pathlib import Path

p = Path(r"c:\Users\aalsa\OneDrive\Desktop\interview (2)\interview11\backend\reports\INTERVIEW_AUDIO_TEST_REPORT.json")
data = json.loads(p.read_text(encoding="utf-8"))
results = data["results"]
fails = [r for r in results if r["result"] == "FAIL"]
passes = [r for r in results if r["result"] == "PASS"]

print("=== LATENCY ===")
totals = [r["timings"]["total_ms"] for r in results]
stts = [r["timings"]["stt_ms"] for r in results]
print("avg_total", round(sum(totals) / len(totals), 1))
print("avg_stt", round(sum(stts) / len(stts), 1))
print("p50", sorted(totals)[len(totals) // 2])
print("p95", sorted(totals)[int(len(totals) * 0.95)])
print("max", max(totals))

print("=== SOFT PASS (stt weak but pass) ===", sum(1 for r in passes if not r["stt_ok"]))
print("=== FAIL by stage ===", dict(Counter(r["failure_stage"] for r in fails)))
print("=== FAIL by condition ===", dict(Counter(r["condition"] for r in fails)))
print("=== FAIL by speaker ===", dict(Counter(r["speaker"] for r in fails)))
print("=== FAIL by Q ===", dict(Counter(r["question_id"] for r in fails)))

print("=== PASS rate speaker x condition ===")
for sp in ["jordanian", "indian", "kuwaiti"]:
    for cond in ["clean", "fast", "office_noise", "far", "poor_call", "combined"]:
        subset = [r for r in results if r["speaker"] == sp and r["condition"] == cond]
        if not subset:
            continue
        ok = sum(1 for r in subset if r["result"] == "PASS")
        print(f"{sp:10} {cond:12} {ok}/{len(subset)}")

print("=== FAIL DETAIL ===")
for r in fails:
    exp = (r.get("expected_question") or "")[:55]
    stt = (r.get("transcript") or "")[:70]
    print(
        f"Q{r['question_id']}|{r['speaker']}|{r['condition']}|{r['failure_stage']}|"
        f"exp={exp}|stt={stt!r}|match={r.get('match_id')}|intent={r['intent_score']}|stt_sc={r['stt_score']}"
    )

# Copy reports to Desktop for easy attach
desktop = Path(r"c:\Users\aalsa\OneDrive\Desktop")
for name in ("INTERVIEW_AUDIO_TEST_REPORT.html", "INTERVIEW_AUDIO_TEST_REPORT.json"):
    src = p.parent / name
    if src.exists():
        (desktop / name).write_bytes(src.read_bytes())
        print("COPIED", desktop / name, src.stat().st_size)
