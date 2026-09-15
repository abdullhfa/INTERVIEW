# V5 — 150 Voice Stress Test Pack

This package contains **150 WAV files** for practical testing of the live interview assistant.

## Design
- 50 semantic intents × 3 accent proxies = 150 files.
- Accent targets: Indian English, Jordanian/Arabic English, Emirati/Gulf English.
- Speech rates: slow, normal, fast, very fast.
- Distance simulation: close, medium, far.
- Environmental conditions: clean, room noise, fan-like noise, keyboard-like noise.
- Question styles: indirect, compound, long, short, direct.
- Audio format: 16 kHz, 16-bit, mono WAV for STT pipelines.

## Important accent limitation
These are **synthetic accent proxies**, not recordings of real people from India, Jordan, or the UAE. They are useful for STT robustness, pronunciation variation, speed, distance, noise, paraphrase, and question-understanding stress testing. They must **not** be treated as proof of real-human accent accuracy. A later human-speaker validation set should still be used before claiming accent performance.

## Most important test
Do not judge only by exact transcript text. For every sample check:
1. Was the important meaning preserved?
2. Was the intended question understood?
3. Was the correct grounded answer selected?
4. Was there a confident wrong answer?
5. Was there a duplicate?
6. What was end-to-end latency?

Use `evaluation_results.csv` to record results.

## Files
- `manifest.csv` — all conditions and ground truth
- `manifest.json` — machine-readable manifest
- `questions_ground_truth.txt` — easy human review
- `evaluation_results.csv` — blank scoring sheet
- `summary.json` — distribution summary
- `audio/indian/` — 50 files
- `audio/jordanian/` — 50 files
- `audio/emirati/` — 50 files
