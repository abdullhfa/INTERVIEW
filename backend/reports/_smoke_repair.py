from app.services.question_bank import question_bank
from app.services.technical_term_repair import repair_technical_terms

question_bank.load(force=True)
samples = [
    "What's R-A-G?",
    "Explain Rod.",
    "What is R-A-B?",
    "What are Godrails?",
    "What are LLM guardrails?",
    "What are gardrails?",
    "What in agency K-I?I.",
    "What in a gigantic I?",
    "Y-Leng-ref and not Leng-Chain.",
    "No chunks down.",
]
for t in samples:
    rep = repair_technical_terms(t)
    m = question_bank.match(t)
    mid = m.entry.id if m else None
    sc = round(m.score, 3) if m else None
    print(repr(t), "=>", repr(rep), "=>", mid, sc)
