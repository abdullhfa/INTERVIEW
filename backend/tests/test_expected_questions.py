from app.models.candidate import ExpectedQuestion
from app.services.expected_questions import match_expected_question, score_question_pair


def test_exact_and_similar_meaning_match():
    items = [
        ExpectedQuestion(
            prompt="Tell me about yourself",
            answer="I am Ahmed and I work in data.",
        )
    ]
    hit = match_expected_question("Can you introduce yourself please?", items)
    assert hit is not None
    assert hit.item.answer.startswith("I am Ahmed")
    assert hit.score >= 0.9


def test_arabic_similar_meaning():
    items = [
        ExpectedQuestion(
            prompt="عرف عن نفسك",
            answer="أنا أحمد وأعمل في البيانات.",
        )
    ]
    hit = match_expected_question("ممكن تعرفنا عن نفسك؟", items)
    assert hit is not None
    assert "أحمد" in hit.item.answer


def test_unrelated_question_does_not_match():
    items = [
        ExpectedQuestion(
            prompt="Tell me about yourself",
            answer="I am Ahmed.",
        )
    ]
    hit = match_expected_question("What is a REST API?", items)
    assert hit is None


def test_token_overlap_custom_question():
    items = [
        ExpectedQuestion(
            prompt="How do you handle production incidents at night?",
            answer="I follow the on-call runbook and call the owner.",
        )
    ]
    hit = match_expected_question(
        "Can you explain how you handle production incidents during the night?",
        items,
    )
    assert hit is not None
    assert "runbook" in hit.item.answer


def test_score_exact_normalize():
    score, reason = score_question_pair(
        "Tell me about yourself!",
        "tell me about yourself",
    )
    assert score == 1.0
    assert reason == "exact"


def test_project_question_similar_meaning():
    items = [
        ExpectedQuestion(
            prompt="what projects have you worked on",
            answer="I built a RAG assistant with LangChain and Chroma.",
        )
    ]
    hit = match_expected_question("شو المشاريع اللي اشتغلتها", items)
    assert hit is not None
    assert "RAG" in hit.item.answer


def test_rag_usage_question_similar_meaning():
    items = [
        ExpectedQuestion(
            prompt="did you use rag in your projects",
            answer="Yes, in the Interview Knowledge Assistant project.",
        )
    ]
    hit = match_expected_question("هل استخدمت ال rag في احدى مشاريعك", items)
    assert hit is not None
    assert "Interview Knowledge Assistant" in hit.item.answer
