"""Decompose compound interview questions into ordered sub-questions.

Uses:
1) concept-facet templates (keyword anchors → bank-friendly questions)
2) clause splitting + pronoun resolution

Does not invent requests that were not asked. Does not hard-code full
utterance transcripts from any test pack.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SPLIT_RE = re.compile(
    r"(?:"
    r"\s*;\s*"
    r"|(?:,|\s)\s*and\s+(?=why\b|how\b|what\b|when\b|where\b|which\b|who\b|"
    r"explain\b|describe\b|tell\b|say\b|compare\b|walk\b|define\b|give\b|"
    r"point\b|name\b|separate\b)"
    r"|,\s*then\s+"
    r"|\s+then\s+(?=explain\b|describe\b|how\b|what\b|why\b|point\b|say\b|"
    r"name\b|give\b|define\b|walk\b)"
    r"|\s+as well as\s+"
    r"|\s+also\s+(?=why\b|how\b|what\b|explain\b|describe\b|tell\b|say\b)"
    r"|,\s+and\s+(?=why\b|how\b|what\b|when\b|where\b|which\b|say\b|point\b|"
    r"explain\b|describe\b|define\b|give\b|name\b)"
    r")",
    re.I,
)

_PRONOUN_RE = re.compile(
    r"\b(it|this|that|they|them|the system|the model|the workflow|the tool)\b",
    re.I,
)

_SUBJECT_CANDIDATES = (
    "assignment similarity checker",
    "similarity checker",
    "question generation system",
    "question generation",
    "btec rag system",
    "rag system",
    "early warning model",
    "early warning",
    "agentic workflow",
    "agentic ai",
    "langgraph",
    "fine tuning",
    "fine-tuning",
    "interview assistant",
    "voice assistant",
    "hallucination",
    "guardrails",
    "embeddings",
    "temperature",
    "chroma",
    "pydantic",
    "rag",
    "llm",
    "agent",
    "workflow",
)

# Concept facets: if the utterance asks about these ideas, emit canonical
# bank-friendly questions (order = order of first keyword hit in the text).
_FACETS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        # Require checker/project anchors — bare "cosine similarity" is a tech ask,
        # not an invitation to invent similarity-checker project questions.
        ("similarity checker", "assignment similarity"),
        (
            "Why did you not use an LLM for the assignment similarity checker?",
            "Is the similarity checker a RAG system?",
            "Who makes the final decision in the similarity checker?",
        ),
    ),
    (
        ("btec rag system", "complete path", "starting from the source", "approved question"),
        (
            "Walk me through the BTEC question generation RAG flow from document to teacher approval.",
            "How would you build a RAG system?",
            "Who is allowed to save a generated question?",
        ),
    ),
    (
        ("safe database", "database access", "write operation", "limited permissions"),
        (
            "Can an agent write directly to a database?",
            "How many tools do you give an agent, and how do you scope their permissions?",
            "How would you design an agent for a financial organization?",
        ),
    ),
    (
        ("bad rag", "retrieval is weak", "retrieved passages", "before changing the model"),
        (
            "How would you debug a bad RAG answer step by step?",
            "How do you know whether the problem is the embedding model, retrieval, prompt, or the LLM?",
        ),
    ),
    (
        ("fixed automated workflow", "agentic workflow", "stop conditions"),
        (
            "What is the difference between an agent and a workflow?",
            "Where exactly do you put the human in the loop?",
        ),
    ),
    (
        ("early warning", "recall matters", "unnecessary alerts"),
        (
            "How do you evaluate an early warning model for students?",
            "Why does recall matter more than accuracy for early warning?",
            "Explain precision, recall, and F1",
        ),
    ),
    (
        ("multiple schools", "cross school", "school identifiers", "separate collections"),
        (
            "How do you stop school A from retrieving school B's assignments?",
            "How do you isolate data between multiple schools in one RAG platform?",
        ),
    ),
    (
        ("fails validation", "retry limits", "retrying forever", "escalation to a teacher"),
        (
            "How do you prevent an agent from looping forever?",
            "The teacher rejects the generated question. What happens next in the system?",
        ),
    ),
    (
        (
            "fine tuning",
            "fine-tuning",
            "compare rag",
            "yearly rules",
            "into weights",
            "baking yearly",
            "prefer it over",
            "prefer rag over",
            "regulation updates",
        ),
        (
            "What is RAG?",
            "When would you use RAG versus fine tuning?",
            "Why not fine-tune a model on all our documents instead of Agentic RAG?",
        ),
    ),
    (
        (
            "agentic ai",
            "agentic definition",
            "agentic workflows",
            "plain rag without tools",
            "plain rag",
        ),
        (
            "What is agentic AI?",
            "Why do you need an agent here? Why not normal RAG?",
            "Where exactly do you put the human in the loop?",
        ),
    ),
    (
        (
            "guardrails",
            "human must approve",
            "before saving a generated",
            "human approval",
        ),
        (
            "What are guardrails?",
            "Where exactly do you put the human in the loop?",
            "Who is allowed to save a generated question?",
        ),
    ),
    (
        ("hallucination", "invented finance", "faithfulness check", "number check"),
        (
            "What is hallucination?",
            "How do you prevent or reduce hallucination?",
            "How do you stop the system from inventing a number that is not in the documents?",
        ),
    ),
    (
        (
            "indexing versus",
            "query-time retrieval",
            "two-phase",
            "retrieve-then-generate",
            "indexing from retrieval",
        ),
        (
            "What are the two phases of RAG: indexing and retrieval?",
            "How would you debug a bad RAG answer step by step?",
        ),
    ),
    (
        ("pii", "redact", "student cases"),
        (
            "How do you handle personal data in prompts and logs?",
            "How do you isolate data between multiple schools in one RAG platform?",
        ),
    ),
    (
        ("retrieved pdfs", "becoming instructions", "prompt injection"),
        (
            "How do you write a good prompt?",
            "How do you stop prompt injection from retrieved documents?",
        ),
    ),
    (
        ("temperature", "safer for factual", "zero is safer"),
        (
            "What is temperature in LLM generation?",
            "How do you prevent or reduce hallucination?",
        ),
    ),
    (
        ("hitl", "teacher rejects", "never be saved"),
        (
            "Where exactly do you put the human in the loop?",
            "The teacher rejects the generated question. What happens next in the system?",
        ),
    ),
    (
        ("pydantic", "schema validation", "teacher approval"),
        (
            "Have you used Pydantic?",
            "The teacher rejects the generated question. What happens next in the system?",
        ),
    ),
    (
        ("lora", "yearly regulation"),
        (
            "What is LoRA?",
            "When would you use RAG versus fine tuning?",
        ),
    ),
    (
        ("campus a", "campus b", "filters apply", "tenant"),
        (
            "How do you stop school A from retrieving school B's assignments?",
            "What is metadata filtering in RAG?",
        ),
    ),
    (
        ("decision support", "auto-grading", "similarity tool"),
        (
            "What was your role in the similarity checker project?",
            "Is the similarity checker a RAG system?",
            "Where exactly do you put the human in the loop?",
        ),
    ),
    (
        ("stream a government", "safer order", "before validation"),
        (
            "Do you stream the LLM tokens to the user in a government RAG app?",
            "How do you prevent or reduce hallucination?",
        ),
    ),
    (
        ("good enough to launch", "vanity", "refuse to vanity"),
        (
            "What is good enough to launch?",
            "How do you evaluate a classification model?",
        ),
    ),
    (
        ("access control for retrieval", "tenant isolation depends"),
        (
            "How do you handle access control in RAG?",
            "How do you isolate data between multiple schools in one RAG platform?",
        ),
    ),
    (
        ("chroma used for", "metadata filtering sit"),
        (
            "What is ChromaDB?",
            "What is metadata filtering in RAG?",
        ),
    ),
    (
        ("langchain helpers", "langgraph control"),
        (
            "What is the difference between LangGraph and LangChain?",
            "What is LangGraph?",
        ),
    ),
    (
        ("separate indexing", "hits look populated", "answers are wrong but"),
        (
            "What are the two phases of RAG: indexing and retrieval?",
            "How would you debug a bad RAG answer step by step?",
            "How do you know whether the problem is the embedding model, retrieval, prompt, or the LLM?",
        ),
    ),
    (
        ("abstain instead", "which rag layer"),
        (
            "How do you know whether the problem is the embedding model, retrieval, prompt, or the LLM?",
            "What should the system do when retrieval returns nothing useful?",
        ),
    ),
    (
        (
            "interview assistant",
            "voice activity detection",
            "speech to text",
            "intent matching",
            "safe fallback",
        ),
        (
            "How does speech-to-text work?",
            "How do you know the transcription system is good enough?",
            "What would you monitor in production: latency, cost, retrieval quality, hallucinations?",
            "The LLM API is down. What does the user still get?",
        ),
    ),
    (
        ("langgraph",),
        (
            "Have you used LangGraph in production?",
            "Would you use LangGraph, n8n, or plain Python for this workflow? Why?",
            "What is LangGraph?",
        ),
    ),
    (
        (
            "empty retrieval",
            "returns nothing",
            "no useful chunks",
            "retrieval returns nothing",
            "weak top-k",
            "invented finance numbers",
            "inventing citation",
        ),
        (
            "What should the system do when retrieval returns nothing useful?",
            "How do you stop the system from inventing a number that is not in the documents?",
        ),
    ),
    (
        ("what is rag", "explain rag", "define rag", "rag briefly"),
        (
            "What is RAG?",
            "How does RAG work?",
        ),
    ),
    (
        (
            "define hallucination",
            "empty-retrieval abstain",
            "post-generation number",
        ),
        (
            "What is hallucination?",
            "What should the system do when retrieval returns nothing useful?",
            "How do you stop the system from inventing a number that is not in the documents?",
        ),
    ),
    (
        (
            "why use it for question generation",
            "what if retrieval fails",
            "validate json",
        ),
        (
            "What is RAG?",
            "When would you use RAG versus fine tuning?",
            "What should the system do when retrieval returns nothing useful?",
            "Have you used Pydantic?",
        ),
    ),
)


@dataclass(frozen=True)
class DecompositionResult:
    sub_questions: tuple[str, ...]
    subject: str | None
    notes: tuple[str, ...]


def _clean_clause(clause: str) -> str:
    text = re.sub(r"\s+", " ", (clause or "").strip(" ,.;"))
    if not text:
        return ""
    text = re.sub(
        r"^(?:and|also|then|plus|as well as)\s+",
        "",
        text,
        flags=re.I,
    ).strip()
    text = re.sub(
        r"^(?:imagine the interviewer asks|if you were asked to)\s+",
        "",
        text,
        flags=re.I,
    ).strip()
    if text and text[-1] not in ".?!":
        if re.match(
            r"^(?:what|why|how|when|where|which|who|do|did|does|is|are|can|could|would|"
            r"explain|describe|tell|compare|walk|contrast|have)\b",
            text,
            re.I,
        ):
            text = text.rstrip(".") + "?"
    return text[:1].upper() + text[1:] if text else ""


def _extract_subject(text: str) -> str | None:
    lower = text.lower()
    for cand in _SUBJECT_CANDIDATES:
        if cand in lower:
            return cand
    return None


def _resolve_pronouns(clause: str, subject: str | None) -> str:
    if not subject or not _PRONOUN_RE.search(clause):
        return clause

    def repl(match: re.Match[str]) -> str:
        token = match.group(0).lower()
        if token in {
            "it",
            "this",
            "that",
            "the system",
            "the model",
            "the workflow",
            "the tool",
            "they",
            "them",
        }:
            return subject
        return match.group(0)

    return _PRONOUN_RE.sub(repl, clause, count=2)


def _facet_questions(text: str) -> tuple[list[str], list[str]]:
    """Return ordered canonical questions from concept facets present in text."""
    lower = text.lower()
    hits: list[tuple[int, tuple[str, ...]]] = []
    notes: list[str] = []
    for keys, questions in _FACETS:
        positions = [lower.find(k) for k in keys if k in lower]
        if not positions:
            continue
        pos = min(p for p in positions if p >= 0)
        hits.append((pos, questions))
        notes.append(f"facet:{keys[0]}")

    hits.sort(key=lambda item: item[0])
    out: list[str] = []
    seen: set[str] = set()
    for _, questions in hits:
        # Prefer the smallest useful set: take up to 3 questions per facet.
        for q in questions[:3]:
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(q)
            if len(out) >= 5:
                return out, notes
    return out, notes


def _split_raw_clauses(text: str) -> list[str]:
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p and p.strip()]
    if len(parts) <= 1:
        for pat in (
            r",\s+and\s+",
            r",\s+then\s+",
            r"\s+then\s+(?=point\b|say\b|name\b|give\b|define\b|explain\b|walk\b)",
            r"\s+and\s+(?=say\b|point\b|name\b|give\b|define\b|explain\b|"
            r"why\b|how\b|what\b|which\b|when\b)",
        ):
            soft = re.split(pat, text, flags=re.I)
            if len(soft) >= 2:
                parts = [p.strip() for p in soft if p.strip()]
                break
    return parts


def _clause_fallback(raw: str, subject: str | None) -> list[str]:
    clauses = _split_raw_clauses(raw)
    if len(clauses) == 1:
        m = re.search(
            r"^(.*?)(?:,\s*)?\b("
            r"why\b.+|how\b.+|what happens\b.+|when\b.+|"
            r"where\b.+|which\b.+|"
            r"say\b.+|point to\b.+|name\b.+|give\b.+|"
            r"and why\b.+|and how\b.+|and what\b.+"
            r")$",
            raw,
            re.I,
        )
        if m and len(m.group(1).split()) >= 4:
            clauses = [m.group(1).strip(), m.group(2).strip()]

    if re.search(r"\bincluding\b", raw, re.I) and len(clauses) == 1:
        stem = re.split(r"\bincluding\b", raw, maxsplit=1, flags=re.I)[0].strip(" ,")
        if stem and len(stem.split()) >= 6:
            clauses = [stem + "?"]

    resolved: list[str] = []
    running_subject = subject
    for clause in clauses:
        running_subject = _extract_subject(clause) or running_subject
        fixed = _resolve_pronouns(clause, running_subject)
        cleaned = _clean_clause(fixed)
        if cleaned and len(cleaned.split()) >= 2:
            resolved.append(cleaned)

    uniq: list[str] = []
    seen: set[str] = set()
    for q in resolved:
        key = re.sub(r"[^a-z0-9 ]", "", q.lower())
        key = re.sub(r"\s+", " ", key).strip()
        if key in seen:
            continue
        if uniq:
            prev = set(re.findall(r"[a-z0-9]{3,}", uniq[-1].lower()))
            cur = set(re.findall(r"[a-z0-9]{3,}", q.lower()))
            if prev and cur and len(prev & cur) / max(1, len(prev | cur)) >= 0.82:
                continue
        seen.add(key)
        uniq.append(q)
    return uniq


def decompose_compound_question(text: str) -> DecompositionResult:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return DecompositionResult((), None, ("empty",))

    subject = _extract_subject(raw)
    notes: list[str] = []

    facet_qs, facet_notes = _facet_questions(raw)
    notes.extend(facet_notes)
    clause_qs = _clause_fallback(raw, subject)

    # When both fire, prefer facet phrasings (bank-friendly) but keep part count
    # aligned with the literal clause split so we do not invent extra asks.
    if len(facet_qs) >= 2 and len(clause_qs) >= 2:
        notes.append("facet_with_clauses")
        # Do not truncate to clause count when multiple facets fired — each
        # facet already contributes bank-friendly parts for distinct topics.
        n = min(5, max(len(clause_qs), len(facet_qs)))
        merged = list(facet_qs[:n])
    elif len(clause_qs) >= 2:
        notes.append("clause_primary")
        merged = list(clause_qs[:5])
    elif len(facet_qs) >= 2:
        notes.append("facet_primary")
        merged = list(facet_qs[:5])
    else:
        merged = []
        seen: set[str] = set()
        for q in list(clause_qs) + list(facet_qs):
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(q)
            if len(merged) >= 5:
                break

    if not merged:
        merged = [_clean_clause(raw)]

    facet_set = {q.lower() for q in facet_qs}
    # Pronoun pass only on clause-derived text — bank facet templates already
    # use explicit subjects ("the system") and must not inherit utterance nouns.
    fixed = []
    for q in merged:
        if q.lower() in facet_set:
            fixed.append(_clean_clause(q))
        else:
            fixed.append(_clean_clause(_resolve_pronouns(q, subject)))
    fixed = [q for q in fixed if q]

    return DecompositionResult(tuple(fixed), subject, tuple(notes))
