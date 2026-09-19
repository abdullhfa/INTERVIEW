"""One-shot: adopt LangChain.docx into technical_ai_senior (answers + new entries)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "app" / "data" / "question_bank" / "technical_ai_senior.json"
BAK = ROOT / "app" / "data" / "question_bank_pre_langchain_docx"

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
    topic: str = "langchain",
    followup_en: str = "",
) -> None:
    if eid in by:
        print("SKIP", eid)
        return
    NEWS.append(
        {
            "id": eid,
            "category": "technical.agents",
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
    "tech.what_is_langchain",
    "LangChain is a framework for building LLM-powered applications and AI agents.",
    "LangChain إطار لبناء تطبيقات مدعومة بالنماذج اللغوية ووكلاء الذكاء الاصطناعي.",
)
upd(
    "tech.what_is_langgraph",
    "LangGraph is a framework for building stateful and complex AI agent workflows.",
    "LangGraph إطار لبناء سير عمل وكلاء ذكاء اصطناعي معقّد وحافظ للحالة.",
)
upd(
    "tech.langgraph_vs_langchain",
    "LangChain helps build LLM applications and agents, while LangGraph gives more control over complex and stateful agent workflows.",
    "LangChain يساعد في بناء تطبيقات ووكلاء النماذج اللغوية، بينما LangGraph يعطي تحكماً أكبر في سير العمل المعقّد والحافظ للحالة.",
    followup_en="Remember: LangChain = Build and integrate. LangGraph = Control and orchestrate.",
)

# hard.checkpoint_vs_memory lives in hard_scenarios.json — update separately after write.

# --- New LangChain entries ---
add(
    "tech.langchain_why",
    "Why do we use LangChain?",
    ["why do we use langchain", "why use langchain", "why langchain"],
    ["langchain", "tools", "prompts", "connect"],
    "We use LangChain to connect LLMs with tools, prompts, data sources, and other application components.",
    "نستخدم LangChain لربط النماذج بالأدوات والـ prompts ومصادر البيانات ومكوّنات التطبيق.",
)
add(
    "tech.langchain_components",
    "What are the main components of LangChain?",
    [
        "what are the main components of langchain",
        "langchain components",
        "main components of langchain",
    ],
    ["models", "prompts", "tools", "agents", "embeddings", "middleware"],
    "Models, prompts, tools, agents, messages, embeddings, and middleware.",
    "النماذج، والـ prompts، والأدوات، والوكلاء، والرسائل، والتضمينات، والـ middleware.",
)
add(
    "tech.langchain_model",
    "What is a model in LangChain?",
    ["what is a model in langchain", "langchain model"],
    ["model", "llm", "langchain"],
    "A model is the LLM used to understand input and generate responses.",
    "النموذج هو الـ LLM المستخدم لفهم المدخل وتوليد الردود.",
)
add(
    "tech.langchain_prompt",
    "What is a prompt in LangChain?",
    ["what is a prompt in langchain", "langchain prompt"],
    ["prompt", "instructions", "context"],
    "A prompt contains the instructions and context sent to the LLM.",
    "الـ prompt يحتوي التعليمات والسياق المرسلين إلى النموذج.",
)
add(
    "tech.langchain_tool",
    "What is a tool in LangChain?",
    ["what is a tool in langchain", "langchain tool"],
    ["tool", "function", "agent"],
    "A tool is a function that an agent can call to perform an action.",
    "الأداة دالة يستطيع الوكيل استدعاءها لتنفيذ فعل.",
)
add(
    "tech.langchain_agent",
    "What is an agent in LangChain?",
    ["what is an agent in langchain", "langchain agent"],
    ["agent", "llm", "tools"],
    "An agent uses an LLM to decide when and which tools to use.",
    "الوكيل يستخدم نموذجاً لغوياً ليقرر متى وأي أدوات يستخدم.",
)
add(
    "tech.langchain_agent_how",
    "How does a LangChain agent work?",
    [
        "how does a langchain agent work",
        "how do langchain agents work",
        "explain langchain agent loop",
    ],
    ["agent", "model", "tools", "loop"],
    "The agent receives a request, calls the model, selects tools if needed, gets the results, and continues until the task is complete.",
    "الوكيل يستلم طلباً، يستدعي النموذج، يختار أدوات إن لزم، يأخذ النتائج، ويكمل حتى تنتهي المهمة.",
    followup_en="LangChain's current create_agent runs a model-and-tool loop until a stopping condition is reached.",
)
add(
    "tech.langchain_create_agent",
    "What is create_agent in LangChain?",
    ["what is create_agent in langchain", "create_agent", "langchain create_agent"],
    ["create_agent", "agent", "tools", "prompts"],
    "create_agent is used to create an AI agent with a model, tools, prompts, and other controls.",
    "create_agent يُستخدم لإنشاء وكيل بنموذج وأدوات وprompts وضوابط أخرى.",
)
add(
    "tech.langchain_middleware",
    "What is middleware in LangChain?",
    [
        "what is middleware in langchain",
        "langchain middleware",
        "why do we use middleware",
        "why use middleware in langchain",
    ],
    ["middleware", "retries", "guardrails", "tool selection"],
    "Middleware lets us control or modify agent behavior during execution.",
    "الـ middleware يتيح التحكم في سلوك الوكيل أو تعديله أثناء التنفيذ.",
    followup_en="We use middleware for things like retries, guardrails, tool selection, and custom logic.",
)
add(
    "tech.langchain_structured_output",
    "What is structured output in LangChain?",
    [
        "what is structured output in langchain",
        "structured output langchain",
        "langchain structured output",
    ],
    ["structured output", "json", "format"],
    "Structured output makes the LLM return data in a defined format, such as JSON.",
    "الخرج المنظم يجعل النموذج يعيد بيانات بصيغة محددة مثل JSON.",
)
add(
    "tech.langchain_multi_llm",
    "Can LangChain work with different LLMs?",
    [
        "can langchain work with different llms",
        "does langchain support multiple providers",
        "langchain openai anthropic google",
    ],
    ["langchain", "openai", "anthropic", "google", "providers"],
    "Yes. LangChain supports different model providers such as OpenAI, Anthropic, and Google.",
    "نعم. LangChain يدعم مزوّدين مثل OpenAI وAnthropic وGoogle.",
)
add(
    "tech.langchain_rag",
    "Can LangChain be used with RAG?",
    [
        "can langchain be used with rag",
        "does langchain support rag",
        "langchain with rag",
    ],
    ["langchain", "rag", "retrievers", "embeddings", "vector"],
    "Yes. LangChain can connect LLMs with retrievers, embeddings, and vector databases.",
    "نعم. LangChain يربط النماذج بالمسترجعات والتضمينات وقواعد المتجهات.",
)
add(
    "tech.langchain_tools_apis",
    "Can LangChain use tools and APIs?",
    [
        "can langchain use tools and apis",
        "does langchain call apis",
        "langchain tools apis databases",
    ],
    ["tools", "apis", "databases", "services"],
    "Yes. LangChain agents can call tools, APIs, databases, and external services.",
    "نعم. وكلاء LangChain يستطيعون استدعاء أدوات وواجهات وقواعد بيانات وخدمات خارجية.",
)
add(
    "tech.langchain_not_only_sequential",
    "Is LangChain only for sequential workflows?",
    [
        "is langchain only for sequential workflows",
        "does langchain only support sequential workflows",
    ],
    ["sequential", "agents", "tool loops"],
    "No. LangChain supports agents and tool loops, not only sequential workflows.",
    "لا. LangChain يدعم الوكلاء وحلقات الأدوات، وليس المسارات التسلسلية فقط.",
)
add(
    "tech.langchain_when_use",
    "When do you use LangChain?",
    [
        "when do you use langchain",
        "when would you use langchain",
        "you have a simple llm application with tools. which framework would you choose",
    ],
    ["when", "langchain", "tools", "rag"],
    "I use LangChain when I need to connect an LLM with tools, prompts, RAG, and other services.",
    "أستخدم LangChain عندما أحتاج ربط نموذج بأدوات وprompts وRAG وخدمات أخرى.",
    followup_en="For a simple LLM application with tools, I would start with LangChain because it provides simple agent and tool integrations.",
)

# --- LangGraph new entries ---
add(
    "tech.langgraph_why",
    "Why do we use LangGraph?",
    ["why do we use langgraph", "why use langgraph", "why langgraph"],
    ["langgraph", "control", "stateful", "non-linear"],
    "We use LangGraph when we need more control over complex, non-linear, and stateful workflows.",
    "نستخدم LangGraph عندما نحتاج تحكماً أكبر في مسارات معقّدة وغير خطية وحافظة للحالة.",
    topic="langgraph",
)
add(
    "tech.langgraph_components",
    "What are the main components of LangGraph?",
    [
        "what are the main components of langgraph",
        "langgraph components",
        "main components of langgraph",
    ],
    ["state", "nodes", "edges"],
    "State, nodes, and edges.",
    "الحالة، والعقد، والحواف.",
    topic="langgraph",
)
add(
    "tech.langgraph_node",
    "What is a node in LangGraph?",
    ["what is a node in langgraph", "langgraph node"],
    ["node", "step", "function"],
    "A node is a processing step or function in the workflow.",
    "العقدة خطوة معالجة أو دالة في سير العمل.",
    topic="langgraph",
)
add(
    "tech.langgraph_edge",
    "What is an edge in LangGraph?",
    ["what is an edge in langgraph", "langgraph edge"],
    ["edge", "transition"],
    "An edge defines the transition from one node to another.",
    "الحافة تعرّف الانتقال من عقدة إلى أخرى.",
    topic="langgraph",
)
add(
    "tech.langgraph_state",
    "What is state in LangGraph?",
    ["what is state in langgraph", "langgraph state"],
    ["state", "shared", "workflow"],
    "State stores the information shared between workflow steps.",
    "الحالة تخزّن المعلومات المشتركة بين خطوات سير العمل.",
    topic="langgraph",
)
add(
    "tech.langgraph_how",
    "How does LangGraph work?",
    ["how does langgraph work", "explain how langgraph works"],
    ["nodes", "edges", "state"],
    "LangGraph uses nodes to perform tasks, edges to control transitions, and state to store workflow information.",
    "LangGraph يستخدم العقد للمهام، والحواف للانتقالات، والحالة لتخزين معلومات سير العمل.",
    topic="langgraph",
)
add(
    "tech.langgraph_conditional_edge",
    "What is a conditional edge?",
    [
        "what is a conditional edge",
        "what is a conditional edge in langgraph",
        "langgraph conditional edge",
    ],
    ["conditional edge", "next node", "state"],
    "A conditional edge chooses the next node based on the current state.",
    "الحافة الشرطية تختار العقدة التالية حسب الحالة الحالية.",
    topic="langgraph",
)
add(
    "tech.langgraph_routing",
    "What is routing in LangGraph?",
    ["what is routing in langgraph", "langgraph routing"],
    ["routing", "next node", "state"],
    "Routing means choosing the next node based on the current state or result.",
    "التوجيه يعني اختيار العقدة التالية حسب الحالة أو النتيجة الحالية.",
    topic="langgraph",
)
add(
    "tech.langgraph_loops",
    "Can LangGraph create loops?",
    [
        "can langgraph create loops",
        "does langgraph support loops",
        "why are loops useful",
        "why are loops useful in langgraph",
    ],
    ["loops", "retry", "validate"],
    "Yes. LangGraph can repeat steps until a condition is satisfied.",
    "نعم. LangGraph يستطيع تكرار الخطوات حتى تتحقق شرط.",
    followup_en="Loops allow agents to retry, validate, or improve results.",
    topic="langgraph",
)
add(
    "tech.langgraph_start",
    "What is START in LangGraph?",
    ["what is start in langgraph", "langgraph start"],
    ["start", "beginning", "graph"],
    "START represents the beginning of the graph.",
    "START يمثل بداية الرسم.",
    topic="langgraph",
)
add(
    "tech.langgraph_end",
    "What is END in LangGraph?",
    ["what is end in langgraph", "langgraph end"],
    ["end", "workflow"],
    "END represents the end of the workflow.",
    "END يمثل نهاية سير العمل.",
    topic="langgraph",
)
add(
    "tech.langgraph_persistence",
    "What is persistence in LangGraph?",
    ["what is persistence in langgraph", "langgraph persistence"],
    ["persistence", "resume", "state"],
    "Persistence saves the graph state so the workflow can continue later.",
    "الاستمرارية تحفظ حالة الرسم حتى يستمر سير العمل لاحقاً.",
    followup_en="LangGraph persistence allows workflows to resume conversations, recover after failure, and support human review.",
    topic="langgraph",
)
add(
    "tech.langgraph_checkpoint",
    "What is a checkpoint in LangGraph?",
    [
        "what is a checkpoint in langgraph",
        "langgraph checkpoint",
        "what is a checkpointer",
        "what is a checkpointer in langgraph",
    ],
    ["checkpoint", "checkpointer", "snapshot"],
    "A checkpoint is a saved snapshot of the graph state.",
    "نقطة التحقق لقطة محفوظة لحالة الرسم.",
    followup_en="A checkpointer saves and restores graph state.",
    topic="langgraph",
)
add(
    "tech.langgraph_thread",
    "What is a thread in LangGraph?",
    [
        "what is a thread in langgraph",
        "langgraph thread",
        "what is thread_id",
        "what is thread id in langgraph",
    ],
    ["thread", "thread_id", "checkpoints"],
    "A thread represents one sequence of graph interactions and checkpoints.",
    "الـ thread يمثل تسلسل تفاعلات ونقاط تحقق للرسم.",
    followup_en="A thread ID identifies the workflow state that should be loaded or continued.",
    topic="langgraph",
)
add(
    "tech.langgraph_short_term_memory",
    "What is short-term memory in LangGraph?",
    [
        "what is short-term memory in langgraph",
        "langgraph short-term memory",
    ],
    ["short-term memory", "thread", "conversation"],
    "Short-term memory keeps information inside the current conversation or thread.",
    "الذاكرة قصيرة المدى تبقي المعلومات داخل المحادثة أو الـ thread الحالي.",
    topic="langgraph",
)
add(
    "tech.langgraph_long_term_memory",
    "What is long-term memory in LangGraph?",
    [
        "what is long-term memory in langgraph",
        "langgraph long-term memory",
    ],
    ["long-term memory", "threads", "store"],
    "Long-term memory stores information that can be reused across different threads.",
    "الذاكرة طويلة المدى تخزّن معلومات يمكن إعادة استخدامها عبر threads مختلفة.",
    topic="langgraph",
)
add(
    "tech.langgraph_hitl",
    "What is Human-in-the-Loop in LangGraph?",
    [
        "what is human-in-the-loop in langgraph",
        "human in the loop langgraph",
        "hitl in langgraph",
    ],
    ["human-in-the-loop", "approve", "review"],
    "Human-in-the-loop allows a human to review, approve, or change an action before the workflow continues.",
    "وجود الإنسان في الحلقة يتيح المراجعة أو الموافقة أو تعديل فعل قبل استمرار سير العمل.",
    topic="langgraph",
)
add(
    "tech.langgraph_interrupt",
    "What is an interrupt in LangGraph?",
    [
        "what is an interrupt in langgraph",
        "langgraph interrupt",
        "when do we use an interrupt",
        "when do you use an interrupt in langgraph",
    ],
    ["interrupt", "pause", "human"],
    "An interrupt pauses the workflow and waits for external input.",
    "الـ interrupt يوقف سير العمل مؤقتاً وينتظر مدخلاً خارجياً.",
    followup_en="We use an interrupt when human approval or input is required.",
    topic="langgraph",
)
add(
    "tech.langgraph_durable_execution",
    "What is durable execution?",
    [
        "what is durable execution",
        "what is durable execution in langgraph",
        "durable execution langgraph",
    ],
    ["durable execution", "resume", "failure"],
    "Durable execution allows a workflow to continue after interruption or failure without starting from the beginning.",
    "التنفيذ المتين يسمح لسير العمل بالاستمرار بعد انقطاع أو فشل دون البدء من الصفر.",
    topic="langgraph",
)
add(
    "tech.langgraph_fault_tolerance",
    "What is fault tolerance in LangGraph?",
    [
        "what is fault tolerance in langgraph",
        "langgraph fault tolerance",
    ],
    ["fault tolerance", "recover", "continue"],
    "Fault tolerance allows the workflow to recover from failures and continue execution.",
    "تحمّل الأعطال يسمح لسير العمل بالتعافي من الفشل ومتابعة التنفيذ.",
    topic="langgraph",
)
add(
    "tech.langgraph_multi_agent",
    "Can LangGraph support multi-agent systems?",
    [
        "can langgraph support multi-agent systems",
        "does langgraph support multi-agent",
        "you have multiple agents with different responsibilities. what would you use",
    ],
    ["multi-agent", "langgraph", "handoff"],
    "Yes. LangGraph can manage multiple agents and control how they communicate and hand off tasks.",
    "نعم. LangGraph يدير عدة وكلاء ويتحكم في تواصلهم وتسليم المهام.",
    followup_en="I would use LangGraph to orchestrate the multi-agent workflow.",
    topic="langgraph",
)
add(
    "tech.langgraph_subgraph",
    "What is a subgraph in LangGraph?",
    ["what is a subgraph in langgraph", "langgraph subgraph"],
    ["subgraph", "workflow"],
    "A subgraph is a smaller graph used inside a larger workflow.",
    "الرسم الفرعي رسم أصغر يُستخدم داخل سير عمل أكبر.",
    topic="langgraph",
)
add(
    "tech.langgraph_agent_as_node",
    "Can each agent be a node?",
    [
        "can each agent be a node",
        "can an agent be a node in langgraph",
        "langgraph agent as node",
    ],
    ["node", "agent", "tool", "llm"],
    "Yes. A node can represent an agent, a tool, an LLM call, or normal code.",
    "نعم. العقدة يمكن أن تمثل وكيلاً أو أداة أو استدعاء نموذج أو كوداً عادياً.",
    topic="langgraph",
)
add(
    "tech.langgraph_when_use",
    "When do you use LangGraph?",
    [
        "when do you use langgraph",
        "when would you use langgraph",
        "you need a workflow with conditional decisions and loops. which framework would you choose",
        "you need human approval before an agent performs an important action. what would you use",
        "you need an agent to resume after a system failure. what would you use",
    ],
    ["when", "langgraph", "state", "loops", "interrupt"],
    "I use LangGraph when I need state, loops, conditional routing, human approval, or complex agent workflows.",
    "أستخدم LangGraph عندما أحتاج حالة وحلقات وتوجيهاً شرطياً وموافقة بشرية أو سير عمل وكلاء معقّد.",
    followup_en="For conditional decisions and loops, human approval with interrupts, or resume after failure with persistence and checkpointing, I choose LangGraph.",
    topic="langgraph",
)
add(
    "tech.langchain_langgraph_together",
    "Can LangChain and LangGraph work together?",
    [
        "can langchain and langgraph work together",
        "is langgraph part of langchain",
        "can i use langgraph without langchain",
        "can you use langgraph without langchain",
    ],
    ["langchain", "langgraph", "together", "independently"],
    "Yes. LangChain agents are built on LangGraph, and we can use both in the same application.",
    "نعم. وكلاء LangChain مبنيون على LangGraph، ويمكن استخدامهما معاً في نفس التطبيق.",
    followup_en="They are separate frameworks, but LangChain agents use LangGraph underneath. LangGraph can also be used independently.",
    topic="langgraph",
)
add(
    "tech.langgraph_infinite_loop",
    "How would you prevent an infinite loop in LangGraph?",
    [
        "how would you prevent an infinite loop in langgraph",
        "prevent infinite loop langgraph",
        "langgraph recursion limit",
    ],
    ["infinite loop", "stopping", "steps"],
    "I would use clear stopping conditions and limit the number of workflow steps.",
    "أستخدم شروط توقف واضحة وأحدّ عدد خطوات سير العمل.",
    topic="langgraph",
)
add(
    "tech.langgraph_tool_error",
    "How would you handle an error in a tool call?",
    [
        "how would you handle an error in a tool call",
        "tool call error handling langgraph",
        "handle tool failure in langgraph",
    ],
    ["error", "retry", "fallback", "validation"],
    "I would add retry, fallback, validation, or route the workflow to an error-handling node.",
    "أضيف إعادة محاولة أو بديلاً أو تحققاً، أو أوجّه سير العمل إلى عقدة معالجة أخطاء.",
    topic="langgraph",
)
add(
    "tech.langsmith_monitor",
    "How would you monitor LangChain or LangGraph applications?",
    [
        "how would you monitor langchain or langgraph applications",
        "what is langsmith",
        "langsmith tracing",
        "monitor langchain langgraph",
    ],
    ["langsmith", "trace", "observability", "latency"],
    "I can use LangSmith to trace agent actions, tool calls, state transitions, errors, and latency.",
    "يمكن استخدام LangSmith لتتبع أفعال الوكيل واستدعاءات الأدوات وانتقالات الحالة والأخطاء والزمن.",
    topic="langgraph",
)

idx = next(i for i, e in enumerate(entries) if e["id"] == "tech.what_is_langchain")
for i, e in enumerate(NEWS):
    entries.insert(idx + 1 + i, e)
    by[e["id"]] = e

raw["entries"] = entries
path.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("TOTAL", len(entries), "new", len(NEWS), "backup", BAK)

# Update hard checkpoint entry (different file)
hard_path = ROOT / "app" / "data" / "question_bank" / "hard_scenarios.json"
shutil.copy2(hard_path, BAK / "hard_scenarios.json")
hard = json.loads(hard_path.read_text(encoding="utf-8"))
h_entries = hard["entries"] if isinstance(hard, dict) else hard
for e in h_entries:
    if e["id"] == "hard.checkpoint_vs_memory":
        e["answer_en"] = (
            "A checkpoint is a saved snapshot of the graph state. Persistence saves graph state "
            "so the workflow can continue later. That is different from RAG memory, which is "
            "documents you search by meaning."
        )
        e["answer_ar"] = (
            "نقطة التحقق لقطة محفوظة لحالة الرسم. الاستمرارية تحفظ الحالة لإكمال العمل لاحقاً. "
            "هذا غير ذاكرة RAG التي تبحث في مستندات بالمعنى."
        )
        print("UPD hard.checkpoint_vs_memory")
        break
if isinstance(hard, dict):
    hard["entries"] = h_entries
    hard_path.write_text(json.dumps(hard, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
else:
    hard_path.write_text(json.dumps(h_entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
