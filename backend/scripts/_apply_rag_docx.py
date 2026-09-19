"""One-shot: adopt RAG.docx into technical_ai_senior (answers + new entries)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "app" / "data" / "question_bank" / "technical_ai_senior.json"
BAK = ROOT / "app" / "data" / "question_bank_pre_rag_docx"

path = BANK
BAK.mkdir(exist_ok=True)
shutil.copy2(path, BAK / "technical_ai_senior.json")

raw = json.loads(path.read_text(encoding="utf-8"))
entries = raw["entries"]
by = {e["id"]: e for e in entries}


def upd(
    eid: str,
    answer_en: str,
    answer_ar: str,
    followup_en: str | None = None,
    aliases_extra: list[str] | None = None,
) -> None:
    e = by[eid]
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
    topic: str = "rag",
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


# --- Updates (similar existing) ---
upd(
    "tech.rag_what",
    "RAG (Retrieval-Augmented Generation) is a technique that retrieves relevant information from external sources and gives it to an LLM before generating an answer.",
    "RAG تقنية تسترجع معلومات ذات صلة من مصادر خارجية وتعطيها للنموذج قبل توليد الجواب.",
    aliases_extra=["what is rag", "what is retrieval augmented generation", "explain rag"],
)

upd(
    "tech.rag_build",
    "In this project, I built a RAG system for PDF documents. First, the system reads the PDF and extracts the text using PyPDF2. Then I split the text into small chunks and convert them into embeddings using an embedding model such as OpenAI or Hugging Face. I store the embeddings in FAISS for similarity search. When the user asks a question, the system retrieves the most relevant chunks. Then LangChain sends the question and the relevant context to the LLM to generate the final answer.",
    "بنيت نظام RAG لمستندات PDF: استخراج النص بـ PyPDF2، تقسيمه إلى أجزاء، تحويلها لتضمينات، تخزينها في FAISS، ثم استرجاع الأجزاء الأقرب وإرسال السؤال والسياق عبر LangChain إلى النموذج للجواب النهائي.",
    followup_en="PDF → extract → chunk → embed → FAISS → retrieve → LLM answer.",
    aliases_extra=["how does rag work", "explain how rag works", "how does a rag system work"],
)

upd(
    "tech.chunking_important",
    "We split documents into chunks to make retrieval faster and help the system find the most relevant information.",
    "نقسّم المستندات إلى أجزاء لتسريع الاسترجاع ومساعدة النظام على إيجاد المعلومات الأكثر صلة.",
    aliases_extra=[
        "why do we split documents into chunks",
        "why split documents into chunks",
        "why chunk documents in rag",
    ],
)

upd(
    "tech.hybrid_search",
    "Hybrid search combines semantic search and keyword search to improve retrieval.",
    "البحث الهجين يجمع البحث الدلالي والبحث بالكلمات المفتاحية لتحسين الاسترجاع.",
    aliases_extra=["what is hybrid search in rag", "hybrid search in rag"],
)

upd(
    "tech.reranking",
    "Reranking means reordering the retrieved chunks to put the most relevant ones first.",
    "إعادة الترتيب تعني إعادة ترتيب الأجزاء المسترجعة لوضع الأكثر صلة أولاً.",
    aliases_extra=["what is reranking in rag", "what is re-ranking in rag", "reranking in rag"],
)

upd(
    "tech.rag_two_phases",
    "Indexing organizes embeddings so the system can search and retrieve relevant information quickly. Retrieval is the live step that finds the best chunks for a question.",
    "الفهرسة تنظّم التضمينات ليبحث النظام ويسترجع بسرعة. الاسترجاع هو الخطوة الحية لإيجاد أفضل الأجزاء للسؤال.",
)

# --- New entries ---
add(
    "tech.rag_why",
    "Why do we use RAG?",
    [
        "why do we use rag",
        "why use rag",
        "why rag",
        "why is rag useful",
    ],
    ["rag", "up-to-date", "hallucination", "relevant"],
    "We use RAG to give the LLM up-to-date and relevant information and reduce hallucination.",
    "نستخدم RAG لإعطاء النموذج معلومات حديثة وذات صلة وتقليل الاختلاق.",
)

add(
    "tech.vector_database_what",
    "What is a vector database in RAG?",
    [
        "what is a vector database in rag",
        "what is a vector database",
        "what is vector db in rag",
        "explain vector database",
    ],
    ["vector database", "embeddings", "similarity", "rag"],
    "A vector database stores embeddings and helps find the most similar information quickly.",
    "قاعدة بيانات المتجهات تخزّن التضمينات وتساعد على إيجاد المعلومات الأكثر تشابهاً بسرعة.",
)

add(
    "tech.rag_retrieve_how",
    "How does RAG find the most relevant information?",
    [
        "how does rag find the most relevant information",
        "how does rag retrieve relevant chunks",
        "how rag finds relevant documents",
    ],
    ["rag", "embedding", "similarity", "chunks", "retrieve"],
    "RAG compares the user question embedding with stored embeddings and retrieves the most similar chunks.",
    "RAG يقارن تضمين سؤال المستخدم بالتضمينات المخزّنة ويسترجع الأجزاء الأكثر تشابهاً.",
)

add(
    "tech.similarity_search_rag",
    "What is similarity search in RAG?",
    [
        "what is similarity search in rag",
        "what is similarity search",
        "explain similarity search in rag",
    ],
    ["similarity search", "chunks", "meaning", "rag"],
    "Similarity search finds the chunks that are closest in meaning to the user question.",
    "بحث التشابه يجد الأجزاء الأقرب معنىً لسؤال المستخدم.",
)

add(
    "tech.faiss_what",
    "What is FAISS in RAG?",
    [
        "what is faiss in rag",
        "what is faiss",
        "explain faiss",
        "why use faiss",
    ],
    ["faiss", "vector", "embeddings", "search"],
    "FAISS is a library used to store and search vector embeddings efficiently.",
    "FAISS مكتبة لتخزين تضمينات المتجهات والبحث فيها بكفاءة.",
)

add(
    "tech.rag_vs_llm",
    "What is the difference between RAG and a normal LLM?",
    [
        "what is the difference between rag and a normal llm",
        "rag vs normal llm",
        "rag versus llm",
        "difference between rag and llm",
    ],
    ["rag", "llm", "trained knowledge", "external"],
    "A normal LLM answers from its trained knowledge, while RAG retrieves external information before generating the answer.",
    "النموذج العادي يجيب من معرفته المدرَّبة، بينما RAG يسترجع معلومات خارجية قبل توليد الجواب.",
)

add(
    "tech.chunk_overlap",
    "What is chunk overlap in RAG?",
    [
        "what is chunk overlap in rag",
        "what is chunk overlap",
        "explain chunk overlap",
        "why use chunk overlap",
    ],
    ["chunk", "overlap", "context", "rag"],
    "Chunk overlap means repeating a small part of text between chunks to keep the context.",
    "تداخل الأجزاء يعني تكرار جزء صغير من النص بين الأجزاء للحفاظ على السياق.",
)

add(
    "tech.topk_rag",
    "What is Top-K in RAG?",
    [
        "what is top-k in rag",
        "what is top k in rag",
        "what is topk in rag",
        "explain top-k retrieval",
    ],
    ["top-k", "topk", "retrieve", "chunks", "rag"],
    "Top-K means retrieving the top K most relevant chunks for the user question.",
    "Top-K يعني استرجاع أفضل K أجزاء ذات صلة بسؤال المستخدم.",
)

add(
    "tech.rag_improve_accuracy",
    "How can we improve RAG accuracy?",
    [
        "how can we improve rag accuracy",
        "how to improve rag",
        "improve rag retrieval accuracy",
        "how do you improve rag quality",
    ],
    ["rag", "chunking", "embeddings", "reranking", "context"],
    "We can improve RAG accuracy by using better chunking, good embeddings, reranking, and retrieving the most relevant context.",
    "نحسّن دقة RAG بتقسيم أفضل وتضمينات جيدة وإعادة ترتيب واسترجاع السياق الأكثر صلة.",
)

add(
    "tech.metadata_rag",
    "What is metadata in RAG?",
    [
        "what is metadata in rag",
        "what is metadata",
        "explain metadata in rag",
        "rag chunk metadata",
    ],
    ["metadata", "file name", "page", "source", "rag"],
    "Metadata is extra information about a chunk, such as the file name, page number, date, or source.",
    "البيانات الوصفية معلومات إضافية عن الجزء مثل اسم الملف ورقم الصفحة والتاريخ أو المصدر.",
)

add(
    "tech.semantic_search_rag",
    "What is semantic search in RAG?",
    [
        "what is semantic search in rag",
        "what is semantic search",
        "explain semantic search in rag",
    ],
    ["semantic search", "meaning", "rag", "embeddings"],
    "Semantic search finds information based on meaning, not only exact keywords.",
    "البحث الدلالي يجد المعلومات حسب المعنى وليس فقط تطابق الكلمات.",
)

add(
    "tech.keyword_search",
    "What is keyword search in RAG?",
    [
        "what is keyword search in rag",
        "what is keyword search",
        "explain keyword search in rag",
        "lexical search in rag",
    ],
    ["keyword search", "exact words", "terms", "rag"],
    "Keyword search finds information by matching exact words or terms in the query.",
    "البحث بالكلمات يجد المعلومات بمطابقة الكلمات أو المصطلحات حرفياً في الاستعلام.",
)

add(
    "tech.indexing_rag",
    "What is indexing in RAG?",
    [
        "what is indexing in rag",
        "what is indexing",
        "explain indexing in rag",
        "rag index",
    ],
    ["indexing", "embeddings", "search", "retrieve", "rag"],
    "Indexing organizes embeddings so the system can search and retrieve relevant information quickly.",
    "الفهرسة تنظّم التضمينات ليبحث النظام ويسترجع المعلومات ذات الصلة بسرعة.",
)

add(
    "tech.grounding_rag",
    "What is grounding in RAG?",
    [
        "what is grounding in rag",
        "what is grounding",
        "explain grounding in rag",
        "grounded answer rag",
    ],
    ["grounding", "retrieved", "source", "rag"],
    "Grounding means generating the answer based on retrieved source information.",
    "التأسيس يعني توليد الجواب بناءً على معلومات المصدر المسترجعة.",
)

add(
    "tech.context_in_rag",
    "What is context in RAG?",
    [
        "what is context in rag",
        "explain context in rag",
        "rag context meaning",
        "what does context mean in rag",
    ],
    ["context", "retrieved", "llm", "question", "rag"],
    "Context is the relevant information retrieved from the data source and sent to the LLM with the user question.",
    "السياق في RAG هو المعلومات ذات الصلة المسترجعة من المصدر والمُرسلة إلى النموذج مع سؤال المستخدم.",
)

idx = next(i for i, e in enumerate(entries) if e["id"] == "tech.rag_what")
for i, e in enumerate(NEWS):
    entries.insert(idx + 1 + i, e)
    by[e["id"]] = e

raw["entries"] = entries
path.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("TOTAL", len(entries), "new", len(NEWS), "backup", BAK)
