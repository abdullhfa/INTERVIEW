# Final Unseen Holdout v3 — novelty proof

122 clips (120 scored + 2 warm-up).

The build verifies, and refuses to write the pack unless:

- no transcript normalizes to a text used in any earlier pack;
- no transcript is within token_set_ratio 90 of an earlier pack text;
- no transcript is a verbatim bank question or alias;
- no transcript repeats inside the pack;
- every gold id exists in the question bank;
- 120 scored clips, 15 per question type, 24 per condition, 30 per accent.

All checks passed at build time.
