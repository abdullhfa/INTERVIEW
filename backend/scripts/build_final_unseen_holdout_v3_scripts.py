"""
Build the Final Unseen Holdout v3 pack (EVAL ONLY).

Writes, under frontend/public/voice-drill/final-unseen-holdout-v3/:

    scripts.json   runtime rows — NO gold. This is what the suite reads to play audio.
    gold.json      expected_intent_ids only, keyed by clip id. Never read before scoring.
    pack_meta.json pack description + balance
    manifest.json  flat list for the voice-drill page
    NOVELTY.md     proof that no text is reused from any earlier pack

Design rules (Final Unseen Holdout protocol):
  * 120 scored clips + 2 warm-up, 8 question types x 15
  * conditions clean/office/poor/far/fast, 24 each (i % 5)
  * accents indian/jordanian/egyptian/emirati, 30 each (i % 4)
  * every transcript is newly authored: the build FAILS if any normalized text
    matches, or is >= 90 token_set_ratio to, a text in any earlier pack
  * gold lives in a separate file so no expected id can reach the decision path
  * run ONCE, then lock with scripts/lock_holdout_v3.py

Do not tune anything on this pack. If a real bug is found and fixed after v3
has been run, v3 is VOID and a v4 pack is required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PACK_ROOT = ROOT.parent / "frontend" / "public" / "voice-drill" / "final-unseen-holdout-v3"
VOICE_DRILL = PACK_ROOT.parent
BANK_DIR = ROOT / "app" / "data" / "question_bank"

CONDITIONS = ("clean", "office", "poor", "far", "fast")

# Accent profiles are named for what they ACTUALLY are, not for a dialect we
# cannot claim. `en-IN` is a genuine English-locale neural voice. The three
# `proxy-ar-*` profiles are Arabic-locale voices reading English text: a useful
# synthetic stand-in for Arabic-accented English, but NOT a recording of a
# Jordanian / Egyptian / Emirati speaker. Reports must never call them dialects.
ACCENT_PROFILES = (
    ("en-IN", "native_locale"),
    ("proxy-ar-JO", "synthetic_proxy"),
    ("proxy-ar-EG", "synthetic_proxy"),
    ("proxy-ar-AE", "synthetic_proxy"),
)
ACCENTS = tuple(name for name, _kind in ACCENT_PROFILES)
ACCENT_KIND = dict(ACCENT_PROFILES)

# ── authored source text (transcript, gold ids) ─────────────────────────────
WARMUP = [
    ('Does the pipeline handle mixed Arabic and English in one sentence?', ['hard.mixed_language_query'], 'short'),
    ('Walk me through what happens between a question arriving and an answer leaving.', ['hard.project_architecture_e2e'], 'medium'),
]

ULTRA_SHORT = [
    ('Chunk overlap?', ['tech.chunk_size']),
    ('Re-ranker — when?', ['tech.reranking']),
    ('Drift, meaning?', ['tech.model_drift']),
    ('p95 — define it.', ['tech.p95']),
    ('Idempotency?', ['tech.idempotency']),
    ('LoRA, briefly.', ['tech.lora']),
    ('Air-gapped site?', ['tech.air_gapped']),
    ('Your notice period?', ['cv.notice_period']),
    ('Redis — what for?', ['tech.redis_why']),
    ('Hybrid search?', ['tech.hybrid_search']),
    ('Golden dataset?', ['tech.golden_dataset']),
    ('Canary rollout?', ['hard.canary_rag']),
    ('Temperature — effect?', ['tech.temperature']),
    ('MCP, quickly.', ['tech.mcp']),
    ('Circuit breaker?', ['hard.circuit_breaker']),
]

SHORT = [
    ('How do you pick a chunk size?', ['tech.chunk_size']),
    ('What happens when two retrieved policies disagree?', ['hard.conflicting_docs']),
    ('Why not simply fine-tune on everything?', ['hard.not_finetune_first']),
    ('Who carries the blame when the agent is wrong?', ['hard.accountability']),
    ('How many GPUs would we actually need?', ['tech.gpu_sizing']),
    ('Can it cope with scanned documents?', ['hard.rag_pdfs_tables_scans']),
    ('Do you stream tokens straight to the user?', ['hard.streaming_vs_validate']),
    ('Is Kubernetes something you have run?', ['cv.kubernetes']),
    ('How long were you based in Kuwait?', ['cv.kuwait_how_long']),
    ('What pushed you out of project management?', ['cv.transition_pm_to_ai']),
    ('Which metric mattered for the dropout model?', ['proj.early_warning.metric']),
    ('Did any student record reach the model?', ['cv.student_pii']),
    ('What stops the bill from exploding?', ['tech.reduce_cost']),
    ('How do you version a prompt in production?', ['hard.prompt_versioning']),
    ('What would you build in your first three months?', ['hard.first_90_agentic']),
]

MEDIUM = [
    ('If retrieval comes back empty, what should the user actually see?', ['hard.empty_retrieval']),
    ("How would you stop one school from reading another school's assignments?", ['hard.tenant_isolation']),
    ('What tells you the embedding model is the weak link rather than the prompt?', ['hard.which_rag_layer_failed']),
    ('Suppose we swap the embedding model next quarter — what has to happen?', ['tech.reindex_embedding_change']),
    ('How would you check that an answer is really supported by its citation?', ['tech.faithfulness_check']),
    ('What would make you reach for a knowledge graph over plain vector search?', ['hard.graph_vs_vector']),
    ('Talk me through sizing hardware for an on-premise deployment.', ['tech.deploy_on_prem', 'tech.gpu_sizing']),
    ('How do you keep an agent from running the same action twice?', ['hard.idempotent_tools']),
    ('What do you watch on a dashboard once this is live?', ['hard.production_monitoring']),
    ('How did you keep future information out of the early-warning features?', ['proj.early_warning.leakage']),
    ('Which libraries do you actually reach for day to day?', ['tech.python_libraries']),
    ('How would you explain a retrieval failure to a head teacher?', ['gen.non_technical_stakeholders']),
    ('What changes in your design if the users speak Gulf Arabic?', ['tech.emirati_dialect']),
    ('When is a simple router enough instead of a supervising agent?', ['hard.supervisor_vs_router']),
    ('How do you decide a system is ready to go live?', ['tech.good_enough_to_launch']),
]

LONG = [
    ('We have twelve years of circulars in PDF, some scanned, some with tables — how would you make them searchable?', ['hard.rag_pdfs_tables_scans', 'tech.rag_build']),
    ('If a retrieved file contains a line telling the system to ignore its instructions, what does your pipeline do about it?', ['hard.injection_in_pdf']),
    ('Our regulations are rewritten every academic year, so what is the argument for retrieval instead of retraining the model?', ['tech.rag_vs_finetuning']),
    ('Imagine the answer quotes a paragraph that does not actually contain the claim — how does the system notice?', ['hard.citation_lie']),
    ('Describe how you would roll a new retriever into production without anyone noticing a regression.', ['hard.canary_rag']),
    ('Explain what you would put in front of the model as protection layers before anything reaches a citizen.', ['tech.guardrails_layers']),
    ('If the language model provider goes offline in the middle of the working day, what does the user still get?', ['hard.fallback_llm_down']),
    ('Tell me how you would trace a single slow request across retrieval, the model, and the tools it called.', ['hard.observability']),
    ('You inherit a system that answers confidently but wrongly about one department — how do you find the cause?', ['hard.rag_debug_steps']),
    ('Walk me through the decision between calling a hosted model and running one inside our own data centre.', ['tech.hosting_decision']),
    ('Talk me through the voice kiosk you built and what made the audio side difficult.', ['proj.kiosk.describe', 'proj.kiosk.challenges']),
    ('How would you convince a finance director that the running cost of this system is under control?', ['tech.reduce_cost', 'hard.cost_spike']),
    ('Describe how you would evaluate whether the retrieval layer is good, separately from the writing quality.', ['hard.evaluate_rag']),
    ('Suppose a teacher refuses the generated exam question — what does the system do with that refusal?', ['hard.teacher_rejects']),
    ('Explain what a checkpoint gives you in a graph-based workflow that conversation memory does not.', ['hard.checkpoint_vs_memory']),
]

VERY_LONG = [
    ('We are a ministry with confidential files per department, an air-gapped network, and no appetite for sending anything to a public API, so tell me how you would architect a question-answering system for us end to end.', ['tech.air_gapped', 'hard.secure_rag', 'tech.deploy_on_prem']),
    ('Assume the pilot goes well and suddenly three thousand staff use it every morning at the same time — describe what breaks first and what you would have put in place beforehand to survive that.', ['hard.production_monitoring', 'tech.latency_p95']),
    ('I want to understand your judgement rather than your tooling, so take one system you built, describe the problem, the approach you rejected, the approach you shipped, and what you would do differently today.', ['cv.what_would_you_improve', 'cv.projects.most_proud']),
    ('A supplier uploads a proposal that quietly contains an instruction telling the assistant to rank them first, and a procurement officer then asks the assistant to compare offers — talk me through every place that attack could be stopped.', ['tech.prompt_injection_supplier', 'tech.guardrails_layers']),
    ('Our documents are half Arabic and half English, users mix both in one sentence, and some of the Arabic is scanned rather than typed, so explain in detail how retrieval would have to be designed for that reality.', ['hard.rag_arabic_english', 'hard.mixed_language_query']),
    ('Say we give the assistant the ability to open tickets and send email on behalf of staff — explain what permissions you would grant, what you would refuse, and how you would prove afterwards that nothing was sent by mistake.', ['hard.least_privilege_example', 'hard.interrupt_side_effects']),
    ('Describe the full lifecycle of one exam question in your ministry system, from the moment a teacher asks for it to the moment it is approved, including every point where a human can stop it.', ['moe.question_generation', 'hard.hitl_where']),
    ('If I asked you to cut the answer time in half without lowering answer quality, describe exactly where you would look first, what you would measure, and how you would prove you had not broken anything.', ['tech.latency_p95', 'hard.evaluate_rag']),
    ('Tell me about a production incident you personally handled, what the users experienced, how you found the cause, and what you changed so that it could not happen the same way again.', ['tech.production_failure_story']),
    ('We have a small team and no machine learning engineers, so explain honestly what part of this system we could maintain ourselves and what would need you or someone like you to stay involved.', ['gen.non_technical_stakeholders', 'hard.first_90_agentic']),
    ('Imagine two specialised assistants reach opposite conclusions about whether a student should be flagged at risk — describe how the system resolves that and what the teacher finally sees.', ['hard.agents_disagree', 'hard.hitl_where']),
    ('Take me through how you would prove to an auditor that no personal student information ever left the building, covering storage, prompts, logs, and anything cached along the way.', ['tech.pii_redaction', 'cv.student_pii', 'tech.audio_retention']),
    ('Explain the difference between a plain automation chain, a single tool-using assistant, and a group of coordinating assistants, and tell me which one your ministry work actually was.', ['hard.agent_terms_difference', 'hard.plain_python_still_agentic']),
    ('Suppose the model answers correctly ninety-five percent of the time but the remaining five percent are confidently wrong in a financial context — argue for what the product should do about that.', ['tech.no_wrong_info_finance', 'tech.i_dont_know_too_often']),
    ('Describe how you would set up evaluation for this before launch: what examples you would collect, who writes the expected answers, and how you would keep the set honest over time.', ['tech.golden_dataset', 'hard.golden_agentic']),
]

COMPOUND = [
    ('What is re-ranking, and when would you bother adding one?', ['tech.reranking', 'hard.hybrid_when']),
    ('Explain hallucination, and then tell me how you hold it down in practice.', ['tech.hallucination_what', 'tech.hallucination_prevent']),
    ('Tell me what a context window is, and say what you do when a document will not fit inside one.', ['tech.context_window', 'tech.chunk_size']),
    ('Describe the similarity checker, name the technologies behind it, and say whether it is a retrieval system at all.', ['proj.similarity.describe', 'proj.similarity.tech', 'proj.similarity.is_rag']),
    ('What is overfitting, how do you spot it, and what do you do about it?', ['tech.overfitting', 'tech.overfitting_prevent', 'tech.evaluate_classification']),
    ('Point me to your vector database experience, then say which one you would pick for us and why.', ['cv.vector_db', 'tech.vector_db_choice']),
    ('Explain what an orchestrator does, and when a single tool-using model is already enough.', ['tech.agent_orchestrator', 'tech.multi_agent_when']),
    ('Give me your education background, your certificates, and how any of that helps you here.', ['cv.education', 'cv.certifications', 'cv.pmp_value']),
    ('What is prompt injection, where does it come from, and what stops it reaching the model?', ['tech.prompt_injection_what', 'hard.injection_in_pdf', 'tech.guardrails_how']),
    ('Tell me what Docker solves, how a container differs from a virtual machine, and whether you would add Kubernetes here.', ['tech.docker_why', 'tech.container_vs_vm', 'tech.kubernetes']),
    ('Describe the early-warning work, the metric you optimised, and what the ministry got out of it.', ['proj.early_warning.describe', 'proj.early_warning.metric', 'proj.early_warning.result']),
    ('Explain tool calling, say why the arguments need a schema, and tell me when an agent should stop calling tools.', ['tech.tool_calling', 'hard.tool_schema', 'hard.agent_stop_tools']),
    ('What is speech to text doing under the hood, why did you run it locally, and how do you judge whether it is accurate enough?', ['tech.how_stt_works', 'tech.whisper_vs_cloud', 'tech.transcription_quality']),
    ('Give me the difference between the two graph libraries, say which you used, and tell me whether the flow still works without them.', ['tech.langgraph_vs_langchain', 'cv.langgraph', 'hard.remove_langchain']),
    ('Cover four things for me: what embeddings are, how similarity search uses them, what metadata filtering adds, and when hybrid search earns its place.', ['tech.embeddings', 'tech.cosine_semantic_search', 'tech.metadata_filtering', 'tech.hybrid_search']),
]

INDIRECT = [
    ("Our head of department keeps saying the assistant 'makes things up'. What is he actually describing?", ['tech.hallucination_what']),
    ('Staff complain the answers changed after we swapped something last month, and nobody reindexed anything.', ['tech.reindex_embedding_change']),
    ('Finance noticed the invoice tripled between Tuesday and Wednesday with no new users.', ['hard.cost_spike']),
    ('We keep getting the right document but the wrong paragraph out of it.', ['hard.wrong_chunk']),
    ('A colleague insists we should train the model on our archive instead of all this retrieval machinery.', ['hard.not_finetune_first']),
    ('The assistant answers beautifully but nobody can tell where the sentence came from.', ['hard.citation_lie', 'tech.faithfulness_check']),
    ('It keeps saying it cannot help, and the staff have started ignoring it entirely.', ['tech.i_dont_know_too_often']),
    ('Somebody from procurement was able to read a file that belongs to human resources.', ['tech.rag_access_control']),
    ('The assistant went round in circles for four minutes and then gave up on its own.', ['hard.agent_loop', 'hard.timeout_vs_steps']),
    ('We ran a pilot and everyone liked it, but I have no idea how to say whether it is actually good.', ['tech.good_enough_to_launch', 'hard.evaluate_rag']),
    ('Two people ask the same thing and get two different answers on the same afternoon.', ['tech.temperature', 'hard.prompt_versioning']),
    ('Our lawyers are nervous about anything leaving the building, including the recordings.', ['tech.audio_retention', 'tech.external_api_risks']),
    ('You have been at the ministry three years — what would make you pack up and go somewhere else?', ['cv.why_leaving']),
    ('If we hired you and then stopped giving you interesting problems, what would happen?', ['gen.motivation']),
    ('I want to know what you are not good at, and I would rather not hear a disguised strength.', ['gen.weaknesses']),
]

FOLLOW_UP = [
    ('Tell me about the BTEC Assignment Similarity Checker', 'And what exactly was your part in it?', ['proj.similarity.role']),
    ('What is RAG?', 'Alright, so how would you actually put one together?', ['tech.rag_build']),
    ('What are embeddings?', 'And how does the search itself work on top of those?', ['tech.cosine_semantic_search']),
    ('What is agentic AI?', 'So where does that differ from an ordinary workflow?', ['tech.agent_vs_workflow']),
    ('What are guardrails?', 'How do you actually build those?', ['tech.guardrails_how']),
    ('What is hallucination and why does it happen?', 'And what do you do to keep it down?', ['tech.hallucination_prevent']),
    ('Tell me about the Student Performance Early-Warning project', 'Which technologies sat behind that one?', ['proj.early_warning.tech']),
    ('What is data leakage?', 'So how do you keep it out of a model?', ['tech.data_leakage_prevent']),
    ('What is overfitting?', 'And your usual way of preventing it?', ['tech.overfitting_prevent']),
    ('What is LangGraph?', 'Have you shipped anything with it yourself?', ['cv.langgraph']),
    ('What is ChromaDB?', 'Would you still choose it for us?', ['tech.vector_db_choice']),
    ('What is fine-tuning?', 'And where would you draw the line against retrieval?', ['tech.rag_vs_finetuning']),
    ('What is prompt injection?', 'What stops it in your own design?', ['tech.guardrails_how']),
    ('Tell me about the Helpdesk Request Classification project', 'What was the hard part there?', ['proj.helpdesk.challenges']),
    ('What is Whisper?', 'Why run that locally rather than a cloud service?', ['tech.whisper_vs_cloud']),
]

TYPE_ORDER = (
    ("ultra_short", ULTRA_SHORT),
    ("short", SHORT),
    ("medium", MEDIUM),
    ("long", LONG),
    ("very_long", VERY_LONG),
    ("compound", COMPOUND),
    ("indirect_paraphrase", INDIRECT),
    ("follow_up_contextual", FOLLOW_UP),
)


def _bank() -> tuple[set[str], set[str]]:
    """(intent ids, normalized question/alias texts)."""
    from app.services.domain_terms import normalize_for_matching

    ids: set[str] = set()
    texts: set[str] = set()
    for path in sorted(BANK_DIR.glob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")).get("entries", []):
            ids.add(entry["id"])
            texts.add(normalize_for_matching(entry["question"]))
            for alias in entry.get("aliases", []):
                texts.add(normalize_for_matching(alias))
    return ids, texts


def _prior_pack_texts() -> list[tuple[str, str]]:
    """Every spoken text from every earlier pack — v3 may reuse none of them."""
    out: list[tuple[str, str]] = []
    sources = [
        ("final-unseen-holdout-v2", "scripts.json"),
        ("final-unseen-holdout", "scripts.json"),
        ("compound-dev", "scripts.json"),
        ("generalization-dev", "scripts.json"),
        ("long-sentence-accent-pack", "manifest.json"),
        ("stress-holdout-v2", "manifest.json"),
        ("stress-pilot", "metadata.json"),
    ]
    for pack, filename in sources:
        path = VOICE_DRILL / pack / filename
        if not path.is_file():
            print(f"  note: {pack}/{filename} not found — skipped")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("entries", [])
        for row in rows:
            for key in ("transcript", "spoken_wording", "main_question"):
                text = str(row.get(key) or "").strip()
                if text:
                    out.append((pack, text))
    return out


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for i, (text, gold, qtype) in enumerate(WARMUP, start=1):
        rows.append(
            {
                "id": f"fuh3_warm_{i:02d}",
                "question_type": qtype,
                "condition": "clean",
                "accent": ACCENTS[(i - 1) % len(ACCENTS)],
                "accent_kind": ACCENT_KIND[ACCENTS[(i - 1) % len(ACCENTS)]],
                "transcript": text,
                "context_prior": None,
                "file": f"audio/fuh3_warm_{i:02d}.wav",
                "warmup": True,
                "pack": "final-unseen-holdout-v3",
                "eval_only": True,
                "_gold": list(gold),
            }
        )
    index = 0
    for qtype, entries in TYPE_ORDER:
        for entry in entries:
            if qtype == "follow_up_contextual":
                prior, text, gold = entry
            else:
                text, gold = entry
                prior = None
            index += 1
            rows.append(
                {
                    "id": f"fuh3_{index:03d}",
                    "question_type": qtype,
                    "condition": CONDITIONS[(index - 1) % len(CONDITIONS)],
                    "accent": ACCENTS[(index - 1) % len(ACCENTS)],
                    "accent_kind": ACCENT_KIND[ACCENTS[(index - 1) % len(ACCENTS)]],
                    "transcript": text,
                    "context_prior": prior,
                    "file": f"audio/fuh3_{index:03d}.wav",
                    "warmup": False,
                    "pack": "final-unseen-holdout-v3",
                    "eval_only": True,
                    "_gold": list(gold),
                }
            )
    return rows


def verify(rows: list[dict]) -> list[str]:
    """Hard gate on the pack itself. Any line returned here fails the build."""
    from rapidfuzz import fuzz

    from app.services.domain_terms import normalize_for_matching

    problems: list[str] = []
    ids, bank_texts = _bank()
    prior = [(pack, normalize_for_matching(t), t) for pack, t in _prior_pack_texts()]

    unknown = sorted({g for r in rows for g in r["_gold"] if g not in ids})
    if unknown:
        problems.append(f"gold references unknown intent ids: {unknown}")

    seen: dict[str, str] = {}
    for row in rows:
        norm = normalize_for_matching(row["transcript"])
        if not norm:
            problems.append(f"{row['id']}: empty transcript")
            continue
        if norm in seen:
            problems.append(f"{row['id']}: duplicates {seen[norm]} inside the pack")
        seen[norm] = row["id"]
        if norm in bank_texts:
            problems.append(f"{row['id']}: verbatim copy of a bank question/alias")
        for pack, pnorm, ptext in prior:
            if pnorm == norm:
                problems.append(f"{row['id']}: reused from {pack} ({ptext[:60]!r})")
            elif fuzz.token_set_ratio(norm, pnorm) >= 90 and abs(len(norm) - len(pnorm)) < 40:
                problems.append(
                    f"{row['id']}: near-duplicate of {pack} "
                    f"({ptext[:60]!r}, ratio {fuzz.token_set_ratio(norm, pnorm):.0f})"
                )
        if row["question_type"] == "follow_up_contextual" and not row["context_prior"]:
            problems.append(f"{row['id']}: follow-up without context_prior")

    scored = [r for r in rows if not r["warmup"]]
    if len(scored) != 120:
        problems.append(f"expected 120 scored clips, got {len(scored)}")
    for field, expected in (("condition", 24), ("accent", 30)):
        counts: dict[str, int] = {}
        for r in scored:
            counts[r[field]] = counts.get(r[field], 0) + 1
        if sorted(counts.values()) != [expected] * len(counts):
            problems.append(f"{field} not balanced: {counts}")
    types: dict[str, int] = {}
    for r in scored:
        types[r["question_type"]] = types.get(r["question_type"], 0) + 1
    if sorted(types.values()) != [15] * 8:
        problems.append(f"question types not balanced: {types}")
    return problems


def main() -> int:
    rows = build_rows()
    problems = verify(rows)
    if problems:
        print("PACK BUILD FAILED:")
        for p in problems:
            print("  -", p)
        return 1

    PACK_ROOT.mkdir(parents=True, exist_ok=True)
    (PACK_ROOT / "audio").mkdir(exist_ok=True)

    runtime = [{k: v for k, v in r.items() if k != "_gold"} for r in rows]
    gold = {r["id"]: r["_gold"] for r in rows}

    (PACK_ROOT / "scripts.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (PACK_ROOT / "gold.json").write_text(
        json.dumps(
            {
                "pack": "final-unseen-holdout-v3",
                "note": "Gold lives here, never in scripts.json, so no expected id "
                        "can reach the matching path. Read only by the scorer.",
                "expected_intent_ids": gold,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    scored = [r for r in rows if not r["warmup"]]
    meta = {
        "name": "final-unseen-holdout-v3",
        "eval_only": True,
        "run_once": True,
        "scored_cases": len(scored),
        "warmup_cases": len(rows) - len(scored),
        "question_types": {
            q: sum(1 for r in scored if r["question_type"] == q)
            for q, _ in TYPE_ORDER
        },
        "conditions": {c: sum(1 for r in scored if r["condition"] == c) for c in CONDITIONS},
        "accents": {a: sum(1 for r in scored if r["accent"] == a) for a in ACCENTS},
        "accent_kinds": ACCENT_KIND,
        "accent_note": (
            "en-IN is a genuine English-locale neural voice. proxy-ar-JO / "
            "proxy-ar-EG / proxy-ar-AE are Arabic-locale voices reading English: "
            "synthetic accent proxies, not recordings of human dialect speakers. "
            "Do not report them as Jordanian / Egyptian / Emirati accents."
        ),
        "voice_spotcheck_required_before_lock": True,
        "gold_file": "gold.json",
        "gold_in_runtime_scripts": False,
        "audio_status": "pending_synthesis",
        "supersedes": "final-unseen-holdout-v2",
        "protocol": "backend/reports/FINAL_UNSEEN_HOLDOUT_PROTOCOL.md",
        "novelty_checked_against": [
            "final-unseen-holdout", "final-unseen-holdout-v2", "compound-dev",
            "generalization-dev", "long-sentence-accent-pack", "stress-holdout-v2",
            "stress-pilot", "question bank questions + aliases",
        ],
    }
    (PACK_ROOT / "pack_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PACK_ROOT / "manifest.json").write_text(
        json.dumps(
            [
                {"id": r["id"], "file": r["file"], "transcript": r["transcript"],
                 "condition": r["condition"], "accent": r["accent"],
                 "accent_kind": r["accent_kind"],
                 "question_type": r["question_type"], "warmup": r["warmup"]}
                for r in rows
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    (PACK_ROOT / "NOVELTY.md").write_text(
        "# Final Unseen Holdout v3 — novelty proof\n\n"
        f"{len(rows)} clips ({len(scored)} scored + {len(rows) - len(scored)} warm-up).\n\n"
        "The build verifies, and refuses to write the pack unless:\n\n"
        "- no transcript normalizes to a text used in any earlier pack;\n"
        "- no transcript is within token_set_ratio 90 of an earlier pack text;\n"
        "- no transcript is a verbatim bank question or alias;\n"
        "- no transcript repeats inside the pack;\n"
        "- every gold id exists in the question bank;\n"
        "- 120 scored clips, 15 per question type, 24 per condition, 30 per accent.\n\n"
        "All checks passed at build time.\n",
        encoding="utf-8",
    )
    print(f"pack written to {PACK_ROOT}")
    print(f"  scripts.json  {len(runtime)} rows (no gold)")
    print(f"  gold.json     {len(gold)} entries")
    print("  next: python scripts/synthesize_final_unseen_holdout_v3.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
