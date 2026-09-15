import json
from pathlib import Path

p = Path("reports/INTERVIEW_AUDIO_TEST_REPORT.json")
d = json.loads(p.read_text(encoding="utf-8"))
s = d["summary"]
print("PASS", s["passed"], s["pass_rate"])
print("STT", s["stt_success"], "Intent", s["intent_success"])
print("recovery", s.get("intent_recovery_rate"), "recovered", s.get("recovered_after_stt_error"))
print("by_condition")
for k, v in s["by_condition"].items():
    print(f"  {k}: {v}")
print("by_speaker")
for k, v in s["by_speaker"].items():
    print(f"  {k}: {v}")
print("stages", s["failure_stages"])
targets = {
    "clean": 0.95,
    "office_noise": 0.90,
    "fast": 0.90,
    "far": 0.85,
    "poor_call": 0.85,
    "combined": 0.60,
}
print("vs targets")
for k, t in targets.items():
    r = s["by_condition"][k]["pass_rate"]
    mark = "OK" if r >= t else "MISS"
    print(f"  {k}: {r:.1%} target {t:.0%}  {mark}")

desktop = Path(r"c:\Users\aalsa\OneDrive\Desktop")
public = Path(r"c:\Users\aalsa\OneDrive\Desktop\interview (2)\interview11\frontend\public\voice-drill")
for name in ("INTERVIEW_AUDIO_TEST_REPORT.html", "INTERVIEW_AUDIO_TEST_REPORT.json"):
    src = Path("reports") / name
    (desktop / name).write_bytes(src.read_bytes())
    if name.endswith(".html"):
        (public / name).write_bytes(src.read_bytes())
print("copied to Desktop + voice-drill")
