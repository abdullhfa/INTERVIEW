"""One-shot: adopt Vector Database.docx into technical bank (+ cv.vector_db answer)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "app" / "data" / "question_bank" / "technical_ai_senior.json"
CV = ROOT / "app" / "data" / "question_bank" / "cv_abdullah.json"
BAK = ROOT / "app" / "data" / "question_bank_pre_vector_db_docx"

BAK.mkdir(exist_ok=True)
shutil.copy2(BANK, BAK / "technical_ai_senior.json")
shutil.copy2(CV, BAK / "cv_abdullah.json")

raw = json.loads(BANK.read_text(encoding="utf-8"))
entries = raw["entries"]
by = {e["id"]: e for e in entries}

cv_raw = json.loads(CV.read_text(encoding="utf-8"))
cv_entries = cv_raw["entries"]
cv_by = {e["id"]: e for e in cv_entries}


def upd(
    store: dict,
    eid: str,
    answer_en: str,
    answer_ar: str,
    followup_en: str | None = None,
    aliases_extra: list[str] | None = None,
) -> None:
    e = store[eid]
    e["answer_en"] = answer_en
    e["answer_ar"] = answer_ar
    if followup_en is not None:
        e["followup_en"] = followup_en
    if aliases_extra:
        aliases = list(e.get("aliases") or [])
        for a in aliases_extra:
            if a not in aliases:
                aliases.insert(0, a)
        e["aliases"] = aliases
    print("UPD", eid)


NEWS: list[dict] = []


def add(
    eid: str,
    question: str,
    aliases: list[str],
    keywords: list[str],
    answer_en: str,
    answer_ar: str,
    *,
    topic: str = "vector_db",
    followup_en: str = "",
    category: str = "technical.rag",
) -> None:
    if eid in by:
        print("SKIP", eid)
        return
    NEWS.append(
        {
            "id": eid,
            "category": category,
            "topic": topic,
            "question": question,
            "aliases": aliases,
            "keywords": keywords,
            "answer_en": answer_en,
            "followup_en": followup_en or answer_en,
            "listen_for": keywords[:6],
            "answer_ar": answer_ar,
        }
    )
    print("ADD", eid)


# --- Updates ---
upd(
    by,
    "tech.vector_database_what",
    "A vector database stores embeddings and finds similar information by meaning.",
    "قاعدة بيانات المتجهات تخزّن التضمينات وتجد المعلومات المتشابهة حسب المعنى.",
    aliases_extra=["what is a vector database", "what is vector database", "explain vector database"],
)

upd(
    by,
    "tech.cosine_semantic_search",
    "Cosine similarity measures how similar two vectors are.",
    "تشابه الجيب تمام يقيس مدى تشابه متجهين.",
    followup_en="Semantic search embeds the question, then finds stored vectors that point in a similar direction.",
    aliases_extra=["what is cosine similarity", "explain cosine similarity"],
)

upd(
    by,
    "tech.embedding_dimension",
    "Vector dimension is the number of values inside an embedding vector.",
    "بُعد المتجه هو عدد القيم داخل متجه التضمين.",
    aliases_extra=["what is vector dimension", "what is the vector dimension", "embedding vector dimension"],
)

upd(
    by,
    "tech.vector_db_choice",
    "Pinecone and Qdrant are full vector databases, Chroma is simple and useful for local RAG, while FAISS is mainly a vector search library.",
    "Pinecone وQdrant قواعد بيانات متجهات كاملة، وChroma بسيطة ومفيدة لـ RAG محلي، بينما FAISS أساساً مكتبة بحث متجهي.",
    aliases_extra=[
        "what is the difference between pinecone qdrant chroma and faiss",
        "pinecone vs qdrant vs chroma vs faiss",
        "difference between pinecone qdrant chroma faiss",
    ],
)

upd(
    cv_by,
    "cv.vector_db",
    "I used FAISS for storing and searching embeddings efficiently.",
    "استخدمت FAISS لتخزين التضمينات والبحث فيها بكفاءة.",
    aliases_extra=[
        "what vector database did you use in your project",
        "which vector database did you use",
        "what vector db did you use",
    ],
)

# --- New entries ---
add(
    "tech.tokens_vs_embeddings",
    "What is the difference between tokens and embeddings?",
    [
        "what is the difference between tokens and embeddings",
        "tokens vs embeddings",
        "tokens versus embeddings",
        "difference between token and embedding",
    ],
    ["tokens", "embeddings", "text", "vectors", "meaning"],
    "Tokens are small parts of text, while embeddings are numerical vectors that represent their meaning.",
    "الرموز أجزاء صغيرة من النص، بينما التضمينات متجهات رقمية تمثّل معناها.",
)

add(
    "tech.vector_db_why",
    "Why do we use a vector database?",
    [
        "why do we use a vector database",
        "why use a vector database",
        "why vector database",
        "why do we need a vector database",
    ],
    ["vector database", "embeddings", "retrieve", "similar"],
    "We use a vector database to store embeddings and quickly retrieve the most similar information.",
    "نستخدم قاعدة بيانات المتجهات لتخزين التضمينات واسترجاع المعلومات الأكثر تشابهاً بسرعة.",
)

add(
    "tech.vector_db_find_how",
    "How does a vector database find similar information?",
    [
        "how does a vector database find similar information",
        "how vector database finds similar",
        "how does vector db search",
    ],
    ["vector", "similarity", "cosine", "compare"],
    "It compares vectors using similarity methods such as cosine similarity.",
    "تقارن المتجهات بطرق تشابه مثل تشابه الجيب تمام.",
)

add(
    "tech.semantic_similarity",
    "What is semantic similarity?",
    [
        "what is semantic similarity",
        "explain semantic similarity",
        "semantic similarity meaning",
    ],
    ["semantic", "similarity", "meaning", "texts"],
    "Semantic similarity measures how close two texts are in meaning.",
    "التشابه الدلالي يقيس مدى قرب نصّين في المعنى.",
)

add(
    "tech.traditional_vs_vector_db",
    "What is the difference between a traditional database and a vector database?",
    [
        "what is the difference between a traditional database and a vector database",
        "traditional database vs vector database",
        "sql vs vector database",
        "exact search vs similarity search",
    ],
    ["traditional", "vector database", "exact", "similarity", "meaning"],
    "A traditional database searches structured data using exact values or conditions, while a vector database searches by similarity and meaning.",
    "قاعدة البيانات التقليدية تبحث في بيانات منظمة بقيم أو شروط دقيقة، بينما قاعدة المتجهات تبحث بالتشابه والمعنى.",
)

add(
    "tech.vector_db_indexing",
    "What is indexing in a vector database?",
    [
        "what is indexing in a vector database",
        "vector database indexing",
        "how does vector db indexing work",
    ],
    ["indexing", "vectors", "faster", "search"],
    "Indexing organizes vectors so the database can search them faster.",
    "الفهرسة تنظّم المتجهات ليبحث فيها قاعدة البيانات بسرعة أكبر.",
)

add(
    "tech.vector_db_factors",
    "What factors do you consider when choosing a vector database?",
    [
        "what factors do you consider when choosing a vector database",
        "how do you choose a vector database",
        "vector database selection criteria",
        "what to consider when choosing vector db",
    ],
    ["scalability", "performance", "integration", "open-source", "cost"],
    "I consider scalability, performance, integration, open-source flexibility, deployment options, and cost.",
    "أراعي قابلية التوسع والأداء والتكامل ومرونة المصدر المفتوح وخيارات النشر والتكلفة.",
)

add(
    "tech.hosting_what",
    "What is Hosting?",
    [
        "what is hosting",
        "explain hosting",
        "what does hosting mean",
    ],
    ["hosting", "server", "websites", "applications"],
    "Hosting is a service that provides server resources to run and store websites or applications.",
    "الاستضافة خدمة توفّر موارد خادم لتشغيل وتخزين مواقع أو تطبيقات.",
    category="technical.infra",
    topic="hosting",
)

add(
    "tech.hosting_types",
    "What are the main types of hosting?",
    [
        "what are the main types of hosting",
        "types of hosting",
        "shared vps dedicated cloud hosting",
    ],
    ["shared", "vps", "dedicated", "cloud", "hosting"],
    "Shared = shared resources. VPS = allocated virtual resources. Dedicated = full physical server. Cloud = scalable and pay as you go.",
    "مشتركة = موارد مشتركة. VPS = موارد افتراضية مخصّصة. مخصّصة = خادم فعلي كامل. سحابية = قابلة للتوسع والدفع حسب الاستخدام.",
    category="technical.infra",
    topic="hosting",
)

add(
    "tech.deploy_docker_webhook_ngrok",
    "What are Docker, webhooks, ngrok, and TLDs, and how are they used in application deployment?",
    [
        "what are docker webhooks ngrok and tlds",
        "docker webhooks ngrok tld deployment",
        "what is ngrok",
        "what is a webhook",
        "what is a tld",
        "dockerfile image container",
    ],
    ["docker", "webhook", "ngrok", "tld", "container", "image"],
    "Docker packages and runs applications consistently. An image is an application template, and a container is a running instance of an image. A webhook receives event notifications automatically. ngrok exposes localhost with a public HTTPS URL. A TLD is a domain ending such as .com, .org, or .net.",
    "Docker يعبّئ التطبيقات ويشغّلها بشكل متسق. الصورة قالب للتطبيق، والحاوية نسخة شغّالة منه. الـ webhook يستقبل إشعارات الأحداث تلقائياً. ngrok يعرض localhost برابط HTTPS عام. وTLD نهاية النطاق مثل .com أو .org أو .net.",
    followup_en="Dockerfile → Image → Container.",
    category="technical.infra",
    topic="deployment",
)

add(
    "tech.icl_vs_finetuning",
    "What is the difference between in-context learning and fine-tuning?",
    [
        "what is the difference between in-context learning and fine-tuning",
        "in-context learning vs fine-tuning",
        "icl versus fine tuning",
        "difference between icl and fine-tuning",
    ],
    ["in-context learning", "fine-tuning", "prompt", "weights"],
    "In-context learning uses examples in the prompt without changing the model, while fine-tuning updates the model weights using training data.",
    "التعلّم ضمن السياق يستخدم أمثلة في الـ prompt دون تغيير النموذج، بينما الضبط الدقيق يحدّث أوزان النموذج ببيانات تدريب.",
    category="technical.llm",
    topic="llm",
)

idx = next(i for i, e in enumerate(entries) if e["id"] == "tech.vector_database_what")
for i, e in enumerate(NEWS):
    entries.insert(idx + 1 + i, e)
    by[e["id"]] = e

raw["entries"] = entries
BANK.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
CV.write_text(json.dumps(cv_raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("TOTAL tech", len(entries), "new", len(NEWS), "backup", BAK)
