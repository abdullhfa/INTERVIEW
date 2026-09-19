"""One-shot: adopt MCP.docx into technical_ai_senior (answers + new entries)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "app" / "data" / "question_bank" / "technical_ai_senior.json"
BAK = ROOT / "app" / "data" / "question_bank_pre_mcp_docx"

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
    topic: str = "mcp",
    followup_en: str = "",
    category: str = "technical.agents",
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
    "tech.mcp",
    "MCP is a standard protocol that allows AI systems to connect with external tools and data sources.",
    "MCP بروتوكول قياسي يتيح لأنظمة الذكاء الاصطناعي الاتصال بأدوات ومصادر بيانات خارجية.",
    followup_en="We use MCP to connect AI systems with different tools and data sources in a standard way.",
)

# Keep function_calling_vs_mcp aligned with the same MCP definition wording
if "tech.function_calling_vs_mcp" in by:
    upd(
        "tech.function_calling_vs_mcp",
        "Function calling lets the LLM call a specific function, while MCP is a standard protocol that allows AI systems to connect with many tools and data sources.",
        "استدعاء الدوال يتيح للنموذج استدعاء دالة محددة، بينما MCP بروتوكول قياسي يربط أنظمة الذكاء الاصطناعي بعدة أدوات ومصادر بيانات.",
    )

# --- New entries ---
add(
    "tech.mcp_components",
    "What are the main components of MCP?",
    [
        "what are the main components of mcp",
        "mcp main components",
        "mcp components",
        "what is host client and server in mcp",
    ],
    ["mcp", "host", "client", "server"],
    "MCP mainly includes a host, a client, and a server.",
    "MCP يتضمن أساساً مضيفاً (host) وعميلاً (client) وخادماً (server).",
    followup_en=(
        "Host: the application that uses the AI model and manages the overall interaction. "
        "Client: the component that communicates with the MCP server. "
        "Server: the component that provides tools, resources, and data to the AI system."
    ),
)

add(
    "tech.mcp_server_provide",
    "What can an MCP Server provide?",
    [
        "what can an mcp server provide",
        "what does an mcp server provide",
        "mcp server tools resources prompts",
        "what does mcp server give",
    ],
    ["mcp", "server", "tools", "resources", "prompts"],
    "An MCP server can provide tools, resources, and prompts to an AI system.",
    "خادم MCP يمكنه تقديم أدوات وموارد وprompts لنظام الذكاء الاصطناعي.",
)

add(
    "tech.mcp_how",
    "How does MCP work?",
    [
        "how does mcp work",
        "explain how mcp works",
        "how mcp connection works",
        "mcp client server flow",
    ],
    ["mcp", "client", "server", "discover", "tools"],
    "The AI application connects through an MCP client to an MCP server, discovers available tools or data, and uses them when needed.",
    "تطبيق الذكاء الاصطناعي يتصل عبر عميل MCP بخادم MCP، يكتشف الأدوات أو البيانات المتاحة، ويستخدمها عند الحاجة.",
)

add(
    "tech.mcp_why",
    "Why do we use MCP?",
    [
        "why do we use mcp",
        "why use mcp",
        "why mcp",
        "why is mcp useful",
    ],
    ["mcp", "standard", "tools", "data sources", "connect"],
    "We use MCP to connect AI systems with different tools and data sources in a standard way.",
    "نستخدم MCP لربط أنظمة الذكاء الاصطناعي بأدوات ومصادر بيانات مختلفة بطريقة قياسية.",
)

anchor = "tech.mcp" if "tech.mcp" in by else "tech.function_calling_vs_mcp"
idx = next(i for i, e in enumerate(entries) if e["id"] == anchor)
for i, e in enumerate(NEWS):
    entries.insert(idx + 1 + i, e)
    by[e["id"]] = e

raw["entries"] = entries
path.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("TOTAL", len(entries), "new", len(NEWS), "backup", BAK)
