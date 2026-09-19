"""One-shot: adopt LLM.docx into technical_ai_senior (answers + new entries)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "app" / "data" / "question_bank" / "technical_ai_senior.json"
BAK = ROOT / "app" / "data" / "question_bank_pre_llm_docx"

path = BANK
BAK.mkdir(exist_ok=True)
shutil.copy2(path, BAK / "technical_ai_senior.json")

raw = json.loads(path.read_text(encoding="utf-8"))
entries = raw["entries"]
by = {e["id"]: e for e in entries}


def upd(eid: str, answer_en: str, answer_ar: str, followup_en: str | None = None) -> None:
    e = by[eid]
    e["answer_en"] = answer_en
    e["answer_ar"] = answer_ar
    if followup_en is not None:
        e["followup_en"] = followup_en
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
    topic: str = "llm",
    followup_en: str = "",
    category: str = "technical.llm",
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


# --- Updates (answer only on similar existing) ---
upd(
    "tech.what_is_llm",
    "An LLM (Large Language Model) is an AI model trained on large amounts of text data to understand and generate human language.",
    "النموذج اللغوي الكبير (LLM) نموذج ذكاء اصطناعي يُدرَّب على كميات كبيرة من النصوص ليفهم اللغة البشرية ويولّدها.",
)

upd(
    "tech.how_llm_works",
    "An LLM works in steps: tokenization splits text into tokens, embeddings turn tokens into vectors, the transformer uses attention to understand context, then it predicts the next token and repeats until it generates a full response.",
    "يعمل النموذج اللغوي بخطوات: التقطيع إلى رموز، التحويل إلى متجهات، الانتباه لفهم السياق، ثم التنبؤ بالرمز التالي مراراً حتى يكتمل الرد.",
    followup_en="Tokenization → Embeddings → Transformer attention → Next-token prediction → Text generation.",
)

upd(
    "tech.context_window",
    "A context window is the maximum number of tokens an LLM can process in one context. A larger window allows more information, but it may increase memory usage and processing time.",
    "نافذة السياق هي الحد الأقصى لعدد الرموز التي يعالجها النموذج في سياق واحد. النافذة الأكبر تسمح بمزيد من المعلومات، لكنها قد تزيد الذاكرة ووقت المعالجة.",
)

upd(
    "tech.hallucination_what",
    "Hallucination is when an LLM generates incorrect or unsupported information. We can reduce it using RAG, reliable data, clear prompts, and validation.",
    "الاختلاق هو توليد معلومات غير صحيحة أو غير مدعومة. نقلّله بالاسترجاع وبيانات موثوقة وprompts واضحة والتحقق.",
)

upd(
    "tech.hallucination_prevent",
    "We can reduce hallucination using RAG, reliable data, clear prompts, and validation.",
    "نقلّل الاختلاق باستخدام الاسترجاع وبيانات موثوقة وprompts واضحة والتحقق من الإجابات.",
)

upd(
    "tech.temperature",
    "Temperature controls the randomness of token selection. Lower values usually give more consistent answers, while higher values allow more variation.",
    "درجة الحرارة تضبط عشوائية اختيار الرموز. القيم المنخفضة تعطي إجابات أكثر ثباتاً، والعالية تسمح بتنوّع أكبر.",
)

upd(
    "tech.fine_tuning_what",
    "Fine-tuning is additional training of a pre-trained model on specific data to improve its performance for a specialized task.",
    "الضبط الدقيق تدريب إضافي لنموذج مدرَّب مسبقاً على بيانات محددة لتحسين أدائه في مهمة متخصصة.",
)

upd(
    "tech.embeddings",
    "Embeddings convert data into numerical vectors, and vector search finds the most similar vectors based on meaning.",
    "التضمينات تحوّل البيانات إلى متجهات رقمية، والبحث المتجهي يجد أقرب المتجهات حسب المعنى.",
)

upd(
    "tech.tool_calling",
    "Function calling allows an LLM to request an external tool or API to perform a task. The application executes the call and returns the result.",
    "استدعاء الدوال يتيح للنموذج طلب أداة أو واجهة خارجية. التطبيق ينفّذ الطلب ويعيد النتيجة.",
)

# --- New entries from LLM.docx (no close bank match) ---
add(
    "tech.llm_capabilities",
    "What determines an LLM's capabilities?",
    [
        "what determines an llm's capabilities",
        "what determines an llms capabilities",
        "why do different llms perform differently",
        "does the size of an llm affect its performance",
        "what affects llm performance",
    ],
    ["capabilities", "architecture", "training data", "model size", "fine-tuning"],
    "The capabilities of an LLM depend on its architecture, training data, model size, and fine-tuning.",
    "قدرات النموذج اللغوي تعتمد على معماريته وبيانات التدريب وحجمه والضبط الدقيق.",
)

add(
    "tech.choose_llm",
    "How do you choose the right LLM for your project?",
    [
        "how do you choose the right llm for your project",
        "how do you choose the right llm",
        "how to choose an llm for a project",
        "كيف تختار النموذج المناسب لمشروعك",
    ],
    ["choose", "task", "accuracy", "speed", "cost", "privacy"],
    "I choose the model based on the task, accuracy, speed, cost, and data privacy requirements.",
    "أختار النموذج حسب المهمة والدقة والسرعة والتكلفة ومتطلبات خصوصية البيانات.",
)

add(
    "tech.llm_cpu_gpu",
    "Can an LLM run on a CPU or GPU, and what is the role of RAM and VRAM?",
    [
        "can an llm run on a cpu or gpu",
        "can llm run on cpu",
        "cpu vs gpu for llm",
        "role of ram and vram for llm",
        "does an llm need a gpu",
    ],
    ["cpu", "gpu", "ram", "vram", "inference"],
    "An LLM can run on a CPU or GPU. The CPU uses system RAM, while the GPU uses VRAM. GPUs are generally faster for large language models.",
    "يمكن تشغيل النموذج على CPU أو GPU. المعالج يستخدم ذاكرة النظام، والبطاقة تستخدم VRAM. البطاقات عادة أسرع للنماذج الكبيرة.",
)

add(
    "tech.llm_examples",
    "Can you give me some examples of Large Language Models?",
    [
        "can you give me some examples of large language models",
        "examples of llms",
        "give examples of large language models",
        "name some llms",
    ],
    ["gpt", "gemini", "claude", "llama", "qwen", "deepseek"],
    "Examples of LLMs include GPT, Gemini, Claude, Llama, Qwen, and DeepSeek.",
    "أمثلة على النماذج اللغوية: GPT وGemini وClaude وLlama وQwen وDeepSeek.",
)

add(
    "tech.model_weights",
    "What is the weight in a neural network or LLM?",
    [
        "what is the weight",
        "what are weights in a neural network",
        "what are model weights",
        "what is a weight in an llm",
    ],
    ["weights", "parameters", "training", "loss"],
    "Weights are learnable parameters that the model updates during training to reduce the loss.",
    "الأوزان معاملات قابلة للتعلّم يحدّثها النموذج أثناء التدريب لتقليل الخسارة.",
)

add(
    "tech.what_is_cnn",
    "What is a Convolutional Neural Network (CNN), and how does it work?",
    [
        "what is a convolutional neural network",
        "what is a cnn",
        "how does a cnn work",
        "explain convolutional neural network",
    ],
    ["cnn", "convolution", "filters", "pooling", "image"],
    "CNN is a deep learning model mainly used for image processing. It uses filters to extract features, pooling to reduce data size, and classification to recognize objects.",
    "شبكة CNN نموذج تعلّم عميق يُستخدم غالباً لمعالجة الصور: مرشحات لاستخراج الميزات، وتجميع لتقليل الحجم، وتصنيف للتعرّف على الأشياء.",
)

add(
    "tech.token_count_how",
    "How is the number of tokens calculated, and does it depend on the tokenization algorithm?",
    [
        "how is the number of tokens calculated",
        "how are tokens counted",
        "does token count depend on the tokenizer",
        "tokenization algorithm token count",
    ],
    ["tokens", "tokenizer", "tokenization", "count"],
    "The number of tokens depends on the tokenization algorithm and the tokenizer used by the model. The tokenizer splits text into smaller units, and each unit is counted as one token.",
    "عدد الرموز يعتمد على خوارزمية التقطيع والـ tokenizer الخاص بالنموذج. النص يُقسَّم إلى وحدات، وكل وحدة تُحسب رمزاً واحداً.",
)

add(
    "tech.quantization",
    "How can we improve LLM performance and hardware utilization?",
    [
        "how can we improve llm performance and hardware utilization",
        "what is quantization",
        "how does quantization help llms",
        "improve llm hardware utilization",
        "fp16 to q8 or q4",
    ],
    ["quantization", "fp16", "q8", "q4", "memory", "inference"],
    "We can improve LLM performance and hardware utilization by using quantization. It reduces model weights from FP16 to Q8 or Q4, reducing memory usage and potentially improving inference speed.",
    "نحسّن الأداء واستخدام العتاد بالتكميم: تقليل الأوزان من FP16 إلى Q8 أو Q4 يقلّل الذاكرة وقد يسرّع الاستدلال.",
)

add(
    "tech.training_vs_inference",
    "What is the difference between training and inference?",
    [
        "what is the difference between training and inference",
        "training vs inference",
        "training versus inference",
        "what is inference in an llm",
    ],
    ["training", "inference", "weights", "learn"],
    "Training is when the model learns from data and updates its weights. Inference is when the trained model generates answers.",
    "التدريب عندما يتعلّم النموذج من البيانات ويحدّث أوزانه. الاستدلال عندما يولّد النموذج المدرَّب الإجابات.",
)

add(
    "tech.system_vs_user_prompt",
    "What is the difference between a system prompt and a user prompt?",
    [
        "what is the difference between a system prompt and a user prompt",
        "system prompt vs user prompt",
        "system versus user prompt",
        "what is a system prompt",
    ],
    ["system prompt", "user prompt", "instructions", "role"],
    "A system prompt defines the model's role and instructions. A user prompt contains the user's request.",
    "الـ system prompt يحدد دور النموذج وتعليماته. الـ user prompt يحتوي طلب المستخدم.",
)

add(
    "tech.hugging_face",
    "What is Hugging Face, and how do you use it in AI projects?",
    [
        "what is hugging face",
        "what is huggingface",
        "how do you use hugging face",
        "hugging face in ai projects",
    ],
    ["hugging face", "models", "datasets", "transformers"],
    "Hugging Face is an AI platform that provides pre-trained models, datasets, and tools for AI applications.",
    "Hugging Face منصة ذكاء اصطناعي تقدّم نماذج مدرَّبة مسبقاً ومجموعات بيانات وأدوات للتطبيقات.",
)

add(
    "tech.what_is_context",
    "What is context in an LLM?",
    [
        "what is context",
        "what is context in an llm",
        "what does context mean for an llm",
        "define context for language models",
    ],
    ["context", "information", "instructions", "response"],
    "Context is the information and instructions available to the LLM when generating a response.",
    "السياق هو المعلومات والتعليمات المتاحة للنموذج عند توليد الرد.",
    followup_en="RAG = give the model external knowledge. Context = information available to the model during the request.",
)

add(
    "tech.rag_vs_context",
    "What is the difference between RAG and context?",
    [
        "what is the difference between rag and context",
        "rag vs context",
        "rag versus context",
        "how is rag different from context",
    ],
    ["rag", "context", "external knowledge", "request"],
    "RAG means giving the model external knowledge. Context is the information available to the model during the request.",
    "RAG يعني إعطاء النموذج معرفة خارجية. السياق هو المعلومات المتاحة للنموذج أثناء الطلب.",
)

add(
    "tech.context_extraction",
    "What is context extraction?",
    [
        "what is context extraction",
        "explain context extraction",
        "what does context extraction mean",
    ],
    ["context", "extraction", "relevant", "information"],
    "Context extraction means finding the most relevant information from data for a specific question or task.",
    "استخراج السياق يعني إيجاد أهم المعلومات ذات الصلة من البيانات لسؤال أو مهمة محددة.",
)

add(
    "tech.sklearn_what",
    "What is Scikit-learn used for?",
    [
        "what is scikit-learn used for",
        "what is sklearn used for",
        "what is scikit learn",
        "why use scikit-learn",
    ],
    ["scikit-learn", "sklearn", "machine learning", "evaluate"],
    "Scikit-learn is a Python library used to build and evaluate machine learning models.",
    "Scikit-learn مكتبة بايثون لبناء نماذج تعلّم الآلة وتقييمها.",
    category="technical.ml",
    topic="ml",
)

add(
    "tech.pandas_what",
    "What is Pandas used for?",
    [
        "what is pandas used for",
        "what is pandas",
        "why use pandas",
        "pandas library",
    ],
    ["pandas", "clean", "organize", "analyze", "data"],
    "Pandas is a Python library used to clean, organize, and analyze data.",
    "Pandas مكتبة بايثون لتنظيف البيانات وتنظيمها وتحليلها.",
    category="technical.ml",
    topic="ml",
)

add(
    "tech.classification_what",
    "What is classification in machine learning?",
    [
        "what is classification in machine learning",
        "what is classification",
        "explain classification in ml",
        "define classification",
    ],
    ["classification", "categories", "labels", "machine learning"],
    "Classification is a machine learning task that assigns data to predefined categories.",
    "التصنيف مهمة تعلّم آلة تُسند البيانات إلى فئات محددة مسبقاً.",
    category="technical.ml",
    topic="ml",
)

add(
    "tech.python_for_ai",
    "Why do you use Python for AI development?",
    [
        "why do you use python for ai development",
        "why python for ai",
        "why use python in machine learning",
        "why is python used for ai",
    ],
    ["python", "ai", "libraries", "machine learning"],
    "Python is easy to use and has many powerful libraries for AI and machine learning.",
    "بايثون سهلة الاستخدام ولها مكتبات قوية كثيرة للذكاء الاصطناعي وتعلّم الآلة.",
    category="technical.ml",
    topic="ml",
)

add(
    "tech.what_is_fastapi",
    "What is FastAPI, and why do you use it?",
    [
        "what is fastapi",
        "what is fastapi and why do you use it",
        "why use fastapi",
        "explain fastapi",
    ],
    ["fastapi", "api", "python", "backend"],
    "FastAPI is a Python framework used to build fast APIs for AI and backend applications.",
    "FastAPI إطار بايثون لبناء واجهات برمجية سريعة لتطبيقات الذكاء الاصطناعي والخلفية.",
    category="technical.ml",
    topic="ml",
)

idx = next(i for i, e in enumerate(entries) if e["id"] == "tech.what_is_llm")
for i, e in enumerate(NEWS):
    entries.insert(idx + 1 + i, e)
    by[e["id"]] = e

raw["entries"] = entries
path.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("TOTAL", len(entries), "new", len(NEWS), "backup", BAK)
