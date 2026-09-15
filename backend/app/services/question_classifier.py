"""
AI Interview Coach - Question Classifier

Classifies interviewer utterances as QUESTION, STATEMENT, FOLLOW_UP, or UNCERTAIN.
Handles imperative-form questions ("Tell me about...", "Explain...").
Filters out acknowledgments ("Okay", "Good", "I understand").
"""

from __future__ import annotations
import logging
import re
from typing import Optional

from app.models.question import (
    UtteranceType,
    UtteranceClassification,
    QuestionCategory,
    QuestionAction,
)
from app.services.gemini_gateway import gemini

logger = logging.getLogger(__name__)

# Utterances that should NEVER trigger an answer
ACKNOWLEDGMENT_PATTERNS = {
    "okay", "ok", "good", "great", "interesting", "i see", "i understand",
    "that makes sense", "right", "sure", "alright", "got it", "understood",
    "perfect", "fine", "thank you", "thanks", "noted", "yes", "yeah", "yep",
    "no", "nope", "mm", "hmm", "uh huh", "aha",
    "mm hmm", "mm-hmm", "mhm", "mmm", "uh-huh", "uhhuh",
    "exactly", "correct", "absolutely", "indeed", "true",
    "that's right", "that is right", "that's correct", "that is correct",
    "that's true", "that is true", "that's good", "that is good",
    "that's fine", "that is fine", "sounds good", "fair enough",
    "okay that's right", "ok that's right", "yes that's right",
    "okay right", "ok right", "right okay", "right ok",
    "okay thanks", "ok thanks", "okay thank you", "ok thank you",
    "thanks that makes sense", "thank you that makes sense",
    "okay thanks that makes sense", "ok thanks that makes sense",
    "حسنًا", "حسنًا", "جيد", "ممتاز", "فهمت", "تمام", "شكرًا", "شكرا",
    "صح", "صحيح", "بالضبط", "تماما", "تمامًا", "كلامك صحيح", "موافق",
}

_LEADING_SOFT_ACK_RE = re.compile(
    r"^(?:ok(?:ay)?|yes|yeah|yep|right|sure|alright|thanks|thank you|"
    r"mm(?:\s*|-*)?hmm|mhm|uh(?:\s*|-*)?huh)"
    r"(?:[,.!]+\s*|\s+)+",
    re.IGNORECASE,
)

_AFFIRMATION_ONLY_RE = re.compile(
    r"^(?:that(?:'s| is)\s+(?:right|correct|true|good|fine)"
    r"|exactly(?:\s+right)?"
    r"|absolutely"
    r"|correct"
    r"|sounds\s+good"
    r"|fair\s+enough"
    r"|بالضبط|صحيح|تماماً?|موافق)"
    r"[.!]*$",
    re.IGNORECASE,
)

GREETING_PATTERNS = {
    "hi", "hello", "hey", "yo", "welcome", "welcome everyone",
    "welcome aboard", "hi everyone", "hello everyone", "hi there",
    "hello there", "hey there", "good morning", "good afternoon",
    "good evening", "how are you", "how's it going", "how are you doing",
    "nice to meet you", "pleased to meet you", "thanks for having me",
    "welcome to the interview", "welcome to our interview",
    "مرحبا", "أهلا", "اهلا", "أهلا وسهلا", "اهلا وسهلا", "يا هلا", "هلا",
    "السلام عليكم", "سلام عليكم", "صباح الخير", "مساء الخير", "حياك الله",
}

# Interview closings must never trigger a technical answer.
CLOSING_PHRASE_MARKERS = (
    "thank you for your time",
    "thanks for your time",
    "thank you so much",
    "thanks so much",
    "thank you very much",
    "thanks very much",
    "have a good day",
    "have a nice day",
    "nice talking to you",
    "nice talking with you",
    "that is all",
    "that's all",
    "that will be all",
    "we are done",
    "we're done",
    "interview is over",
    "end of the interview",
    "شكرا لوقتك",
    "شكراً لوقتك",
    "شكرًا لوقتك",
    "يعطيك العافية",
    "انتهت المقابلة",
    "خلصنا",
)

_LEADING_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|welcome|مرحبا|أهلا|اهلا|هلا)"
    r"(?:\s+(?:everyone|there|all))?"
    r"[,.!]*(?:\s+|$)",
    re.IGNORECASE,
)
_QUESTION_HINT_RE = re.compile(
    r"\b(?:what|why|how|when|where|who|which|explain|tell|describe|walk)\b"
    r"|can you|could you|would you"
    r"|ما |ماذا |كيف |لماذا |هل |اشرح |حدثني",
    re.IGNORECASE,
)

INTRODUCTION_QUESTION_MARKERS = (
    "tell me about yourself",
    "introduce yourself",
    "speak about yourself",
    "speak for yourself",
    "talk about yourself",
    "what is your name",
    "what's your name",
    "whats your name",
    "tell me your name",
    "your name and",
    "name and what is your work",
    "name and your work",
    "your work experience",
    "your work history",
    "years of experience",
    "where you work",
    "where do you work",
    "where you worked",
    "what you did",
    "what did you do",
    "what you do",
    "what do you do",
    "in the past",
    "tell me about your work",
    "tell me about your job",
    "tell me about your role",
    "tell me about your experience",
    "your previous job",
    "your previous role",
    "your current job",
    "your current role",
    "تحدث عن نفسك",
    "حدثني عن نفسك",
    "تكلم عن نفسك",
    "احكي عن نفسك",
    "عرفني بنفسك",
    "عرف عن نفسك",
    "أخبرني عن نفسك",
    "ما اسمك",
    "شو اسمك",
    "ايش اسمك",
    "إيش اسمك",
    "اسمك و",
    "خبرتك العملية",
    "خبرتك المهنية",
    "خبرتك في العمل",
    "وين تشتغل",
    "أين تعمل",
    "وين اشتغلت",
    "أين عملت",
    "شو اشتغلت",
    "ماذا عملت",
    "شو بتشتغل",
    "ماذا تعمل",
    "في الماضي",
    "عملك السابق",
    "عملك الحالي",
)

# STT often prefixes a real question with filler words ("so", "okay", "يعني")
# or produces colloquial Arabic that does not start with a formal interrogative.
# These complete phrases are safe deterministic signals and avoid a 5-6 second
# model classification call for common interview questions.
QUESTION_PHRASES_ANYWHERE = (
    "what is ", "what are ", "what do ", "what does ", "what would ",
    "how do ", "how does ", "how would ", "why is ", "why do ",
    "can you ", "could you ", "would you ", "tell me ", "explain ",
    "describe ", "walk me through ", "difference between ",
    "ما هو", "ما هي", "ما الفرق", "ما معنى", "ماذا يعني", "ماذا يسمى",
    "كيف يمكن", "كيف تعمل", "كيف يشتغل", "كيف بتشتغل", "كيف بيشتغل",
    "لماذا", "هل يمكنك", "اشرح", "وضح",
    "شو ", "شو هو", "ايش ", "إيش ", "ايه ", "إيه ",
    "قارن", "اذكر", "حدثني", "شو يعني", "ايش يعني", "إيش يعني",
    "يعني ايه", "يعني إيه", "بتسمى", "بتسموا",
)

# Deterministic references to a previous turn. These must run before the broad
# obvious-question fast path; otherwise "Can you explain the example more?"
# becomes a brand-new question and loses the example it refers to.
FOLLOW_UP_REFERENCE_PATTERNS = (
    "the example", "this example", "that example", "another example",
    "explain it", "explain that", "explain more", "tell me more",
    "expand on it", "expand on that", "expand on",
    "more about it", "more about that", "more about", "more detail",
    "in more detail", "go deeper", "go further", "the stages",
    "goes through", "walk me through that", "walk through it",
    "elaborate", "what do you mean", "how so", "give me an example",
    "can you give an example", "could you give an example",
    "what else", "anything else", "and then", "go on", "continue",
    "another point", "what more", "tell me more",
    "the project", "this project", "that project", "in the project",
    "on the project", "your role in", "role in the project",
    "what was your role", "what were your tasks", "your tasks in",
    "your responsibilities in", "what did you do in the project",
    "what did you do on the project",
    "المثال", "مثال آخر", "مثال اخر", "اشرح أكثر", "اشرح اكثر",
    "وضح أكثر", "وضح اكثر", "زيدني", "كمل", "المراحل", "هالمراحل",
    "ممكن توضح", "هل يمكنك التوضيح",
    "ماذا تقصد", "ما المقصود", "بالتفصيل", "أعطني مثال", "اعطني مثال",
    "وش بعد", "وش كمان", "ماذا أيضا", "ماذا ايضا",
    "المشروع", "هذا المشروع", "في المشروع", "على المشروع",
    "دورك", "شو دورك", "ما دورك", "ايش دورك", "إيش دورك",
    "مهامك", "مسؤولياتك", "شو عملت في المشروع", "ماذا عملت في المشروع",
)

_DEICTIC_RE = re.compile(
    r"(?:\b(?:it|this|that|they|them|these|those|its)\b)"
    r"|(?:^|\s)(?:هذا|هذه|ذلك|تلك|هيك|هالشي|عنه|عنها|فيها|فيه)(?:\s|$)",
    re.IGNORECASE,
)

# AI/ML questions need their own category so the answer generator selects the
# deeper AI strategy instead of falling back to a generic concise answer. Keep
# these markers specific enough to avoid classifying ordinary software models
# or architecture questions as AI/ML.
AI_ML_QUESTION_MARKERS = (
    "artificial intelligence", "machine learning", "deep learning",
    "large language model", "large language models", "llm", "llms",
    "neural network", "neural networks", "transformer", "attention mechanism",
    "generative ai", "gen ai", "retrieval augmented generation", "rag",
    "embedding", "embeddings", "vector database", "fine-tuning", "fine tuning",
    "prompt engineering", "natural language processing", "nlp",
    "computer vision", "reinforcement learning", "langchain", "langgraph",
    "agentic ai", "ai agent",
    "الذكاء الاصطناعي", "تعلم الآلة", "التعلم الآلي", "التعلم العميق",
    "نموذج لغوي", "نماذج اللغة", "شبكة عصبية", "الشبكات العصبية",
    "الذكاء التوليدي", "معالجة اللغة الطبيعية", "الرؤية الحاسوبية",
    "التعلم المعزز", "هندسة الأوامر", "التضمينات", "قاعدة بيانات متجهية",
)

# Questions about the candidate's own projects / whether they used a tech in work.
PROJECT_CV_QUESTION_MARKERS = (
    "your projects", "your project", "projects you", "project you",
    "what projects", "which projects", "walk me through a project",
    "tell me about a project", "describe your project",
    "did you use", "have you used", "in your project", "in your projects",
    "your role in", "role in the project", "what was your role",
    "your tasks", "your responsibilities in",
    "operational", "currently operational", "is the program", "is the system",
    "ministry of education", "at the ministry", "working now", "works now",
    "مشاريعك", "المشاريع", "مشروعك", "مشاريع",
    "شو المشاريع", "ما المشاريع", "اشرح مشروع", "حدثني عن مشروع",
    "هل استخدمت", "هل استعملت", "هل طبقت",
    "في مشاريعك", "في احد مشاريعك", "في إحدى مشاريعك", "في احدى مشاريعك",
    "دورك", "شو دورك", "ما دورك", "مهامك", "مسؤولياتك",
    "هل يعمل", "يعمل الآن", "يعمل الان", "وزارة التربية", "الوزارة",
    "قيد التشغيل",
)


def strip_leading_greeting(utterance: str) -> str:
    """Drop a leading hi/hello so the remaining question can still be answered."""
    return _LEADING_GREETING_RE.sub("", utterance.strip(), count=1).strip() or utterance.strip()


# UI / TTS / meeting chrome that must never become a question (P2 stop class).
SYSTEM_AUDIO_MARKERS = (
    "your download is ready",
    "download is ready",
    "download ready",
    "playback started",
    "playback has started",
    "click here to start",
    "click here to begin",
    "click here",
    "press the button",
    "recording has started",
    "this meeting is being recorded",
    "you are muted",
    "please unmute",
    "waiting for the host",
    "the host will let you in",
)

# "Yeah, John." / "Okay, Sarah." — acknowledgment + optional name, not a request.
_ACK_WITH_NAME_RE = re.compile(
    r"^(?:yeah|yes|yep|yup|ok|okay|sure|right|alright|thanks|thank you|"
    r"hi|hello|hey|mm hmm|mhm|uh huh)"
    r"(?:[\s,]+[a-zA-Z\u0600-\u06FF'.-]{2,24})?"
    r"[.!]*$"
)


def is_system_audio_or_noise(utterance: str) -> bool:
    """True for system/TTS/meeting chrome and empty noise fragments."""
    normalized = " ".join(utterance.casefold().strip().rstrip(".!,?").split())
    if not normalized:
        return True
    if any(marker in normalized for marker in SYSTEM_AUDIO_MARKERS):
        return True
    # Very short non-request fragments ("uh", "um", single punctuation).
    if len(normalized) <= 2 and normalized not in {"why", "how", "ما", "شو"}:
        return True
    return False


def has_structural_interview_request(utterance: str) -> bool:
    """Fast structural signal that the utterance asks the candidate for an answer.

    Used for STATEMENT fail-closed gating (P2). No semantic / bank work here.
    """
    text = " ".join(utterance.strip().split())
    if not text:
        return False
    if "?" in text or "؟" in text:
        return True
    normalized = text.casefold().rstrip(".!,?")
    if any(phrase in f"{normalized} " for phrase in QUESTION_PHRASES_ANYWHERE):
        return True
    if any(marker in normalized for marker in INTRODUCTION_QUESTION_MARKERS):
        return True
    if _ADDRESSED_QUESTION_RE.search(normalized):
        return True
    if _QUESTION_HINT_RE.search(normalized) and len(normalized.split()) >= 3:
        # Hint words alone are weak; require a bit of substance.
        body = _SENTENCE_LEAD_IN_RE.sub("", normalized.strip().lstrip(".,!"), count=1)
        if _INTERROGATIVE_START_RE.match(body):
            return True
    for sentence in _SENTENCE_SPLIT_RE.split(normalized):
        body = _SENTENCE_LEAD_IN_RE.sub("", sentence.strip().lstrip(".,!"), count=1)
        if _INTERROGATIVE_START_RE.match(body):
            return True
    return False


def is_greeting_or_filler(utterance: str) -> bool:
    """True for greetings and acknowledgments that should not get an answer."""
    normalized = " ".join(utterance.casefold().strip().rstrip(".!,?").split())
    # Normalize casual filler spellings before set membership checks.
    normalized = (
        normalized.replace("mm-hmm", "mm hmm")
        .replace("uh-huh", "uh huh")
        .replace(",", " ")
    )
    normalized = " ".join(normalized.split())
    if not normalized:
        return True
    if is_system_audio_or_noise(utterance):
        return True
    if _ACK_WITH_NAME_RE.match(normalized):
        return True
    if normalized in ACKNOWLEDGMENT_PATTERNS or normalized in GREETING_PATTERNS:
        return True
    # Peel stacked soft acks: "Okay thanks, that makes sense."
    remainder = normalized
    for _ in range(4):
        nxt = _LEADING_SOFT_ACK_RE.sub("", remainder).strip(" .,!")
        if nxt == remainder:
            break
        remainder = nxt
    if not remainder or remainder in ACKNOWLEDGMENT_PATTERNS:
        return True
    # Soft ack + leftover name token only ("yeah john").
    if (
        remainder
        and len(remainder.split()) == 1
        and remainder.isalpha()
        and len(remainder) <= 24
        and not _QUESTION_HINT_RE.search(remainder)
    ):
        return True
    if _AFFIRMATION_ONLY_RE.match(remainder) or _AFFIRMATION_ONLY_RE.match(normalized):
        return True
    if any(marker in normalized for marker in CLOSING_PHRASE_MARKERS):
        return True
    # "Thank you..." / "Thanks..." closings even with STT junk after them.
    if (
        normalized.startswith("thank you")
        or normalized.startswith("thanks")
        or normalized.startswith("شكر")
    ):
        if not _QUESTION_HINT_RE.search(normalized):
            return True
    if any(normalized.startswith(f"{greeting} ") for greeting in GREETING_PATTERNS):
        if not _QUESTION_HINT_RE.search(normalized):
            return True
    return False


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟])\s+")
_SENTENCE_LEAD_IN_RE = re.compile(
    r"^(?:(?:okay|ok|so|and|now|well|um|uh|alright|right|good|great|then|but|also|first|next|"
    r"finally|lastly|طيب|تمام|اوكي|أوكي|يعني|هلا|هلأ)[,\s]+)*"
)
_INTERROGATIVE_START_RE = re.compile(
    r"^(?:what|why|how|when|where|who|whom|whose|which|"
    r"tell me|tell us|explain|describe|elaborate|walk me|walk us|talk about|talk to me|speak about|"
    r"share|give me|give us|let us know|let me know|say something|"
    r"can you|could you|would you|will you|do you|did you|does|are you|were you|have you|has|had|"
    r"is there|are there|was there|were there|is it|is this|is that|"
    r"i want to know|i would like to know|i'd like to know|i want you to|i'd like you to|"
    r"we want to know|we would like to know|we'd like to know|we would like you to|we'd like you to|"
    r"let's talk|lets talk|let's discuss|lets discuss|let's move|lets move|"
    r"ما|ماذا|كيف|لماذا|ليش|هل|حدثني|حدثنا|اشرح|صف|أخبرني|اخبرني|شو|ايش|إيش|ايه|إيه|وين|أين|متى|"
    r"مين|من هو|ممكن|بتقدر|تقدر|خبرنا|خبرني|عرفنا|عرفني|احكي|إحكي)\b"
)
_ADDRESSED_QUESTION_RE = re.compile(
    r"\b(?:your (?:experience|projects?|role|roles|background|work|team|cv|resume|opinion|view|"
    r"thoughts?|approach|career|journey|strengths?|weaknesses?|salary|expectations?|notice)|"
    r"about yourself|introduce yourself|in your (?:opinion|view|experience|projects?|work|career))\b"
)
NON_QUESTION_MIN_WORDS = 8


def is_non_question_monologue(utterance: str) -> bool:
    """True for spoken text that is not addressed to the candidate as a question.

    Guards the live pipeline against captured audio that is not the interviewer
    (adverts, TTS demo text, someone reading a paragraph). Every sentence is
    checked: one interrogative sentence, a question mark, a known question
    phrase, or a reference to the candidate ("your experience") keeps the
    utterance in the question path. Short utterances are never rejected here;
    they are handled by the acknowledgment and follow-up rules.
    """
    text = " ".join(utterance.strip().split())
    if not text or "?" in text or "؟" in text:
        return False
    if len(text.split()) < NON_QUESTION_MIN_WORDS:
        return False
    normalized = text.casefold()
    if any(phrase in f"{normalized} " for phrase in QUESTION_PHRASES_ANYWHERE):
        return False
    if _ADDRESSED_QUESTION_RE.search(normalized):
        return False
    if any(marker in normalized for marker in INTRODUCTION_QUESTION_MARKERS):
        return False
    for sentence in _SENTENCE_SPLIT_RE.split(normalized):
        body = _SENTENCE_LEAD_IN_RE.sub("", sentence.strip().lstrip(".,!"), count=1)
        if _INTERROGATIVE_START_RE.match(body):
            return False
    return True


def looks_like_follow_up(utterance: str, conversation_history: Optional[list[dict]]) -> bool:
    """True when the utterance depends on a previous interviewer/answer turn."""
    if not conversation_history:
        return False
    # Never treat pure acknowledgments as follow-ups ("Okay. That's right.").
    if is_greeting_or_filler(utterance):
        return False
    has_prior_turn = any(
        entry.get("role") in {"interviewer", "suggested_answer"}
        and (entry.get("text") or entry.get("content"))
        for entry in conversation_history
    )
    if not has_prior_turn:
        return False
    normalized = " ".join(
        utterance.casefold().strip().lstrip(".!,?").rstrip(".!,?").split()
    )
    if any(marker in normalized for marker in FOLLOW_UP_REFERENCE_PATTERNS):
        return True
    # Ignore "that" inside affirmations like "that's right".
    if _AFFIRMATION_ONLY_RE.match(normalized):
        return False
    if _DEICTIC_RE.search(normalized):
        # "that's right/correct" is not a content follow-up.
        if re.search(
            r"\bthat(?:'s| is)\s+(?:right|correct|true|good|fine)\b",
            normalized,
        ):
            return False
        return True
    # Short continuer questions only make sense with a previous turn.
    short_continuers = {
        "what else", "anything else", "and", "more", "continue", "go on",
        "next", "why", "how", "example", "another", "else",
        "وش بعد", "وش كمان", "كمان", "وبعدين", "زيادة", "وكمان",
    }
    words = normalized.split()
    if len(words) <= 3 and any(token in short_continuers for token in words):
        if not normalized.startswith(("what is", "what are", "how do", "how does", "why is", "why do")):
            return True
    return False


def last_qa_pair(history: Optional[list[dict]]) -> tuple[str, str]:
    prev_q = ""
    prev_a = ""
    for entry in history or []:
        text = (entry.get("text") or entry.get("content") or "").strip()
        if not text:
            continue
        role = entry.get("role")
        if role == "interviewer":
            prev_q = text
        elif role == "suggested_answer":
            prev_a = text
    return prev_q, prev_a


def bind_follow_up_question(asked: str, history: Optional[list[dict]]) -> str:
    """Make a deictic follow-up explicit so the model cannot start a new topic."""
    prev_q, prev_a = last_qa_pair(history)
    if not prev_q:
        return asked
    short_a = prev_a if len(prev_a) <= 280 else prev_a[:277].rstrip() + "..."
    return (
        f"{asked.strip()}\n\n"
        "IMPORTANT: This is a follow-up. Words such as it, this, that, them, "
        "what else, and the stages refer to the previous question, not a new topic.\n"
        f"Previous question: {prev_q}\n"
        f"Previous answer: {short_a}\n"
        "Answer immediately with the next point about that same topic only. "
        "Do not invent new facts. Do not say the question is open, vague, or unclear. "
        "Do not pick a new topic."
    )


def _format_follow_up_context(history: list[dict]) -> str:
    """Return the most recent interviewer/suggested-answer pair for reference resolution."""
    relevant = [
        entry
        for entry in history[-8:]
        if entry.get("role") in {"interviewer", "suggested_answer"}
        and entry.get("text")
    ]
    return "\n".join(
        f"{entry.get('role', 'unknown').upper()}: {entry.get('text', '')}"
        for entry in relevant[-4:]
    )


def is_introduction_question(utterance: str) -> bool:
    """Recognize common CV-based self-introduction requests without conversation context."""
    normalized = " ".join(utterance.casefold().strip().rstrip(".!,?").split())
    return any(marker in normalized for marker in INTRODUCTION_QUESTION_MARKERS)


def is_ai_ml_question(utterance: str) -> bool:
    """Recognize explicit AI/ML topics before selecting an answer strategy."""
    normalized = " ".join(utterance.casefold().split())
    return any(marker in normalized for marker in AI_ML_QUESTION_MARKERS)


def is_project_cv_question(utterance: str) -> bool:
    """Recognize questions that must be answered from the candidate's projects/CV."""
    normalized = " ".join(utterance.casefold().split())
    return any(marker in normalized for marker in PROJECT_CV_QUESTION_MARKERS)

CLASSIFICATION_SYSTEM_PROMPT = """\
You are an expert interview utterance classifier. Your job is to determine whether
an interviewer's utterance is a QUESTION that requires a candidate's answer, a STATEMENT
that does not, a FOLLOW_UP to a previous question, or UNCERTAIN.

CRITICAL RULES:
1. Commands that require a response ARE questions:
   - "Tell me about yourself" → QUESTION
   - "Explain RAG" → QUESTION
   - "Walk me through your project" → QUESTION
   - "Can you elaborate?" → FOLLOW_UP
   - "Why?" → FOLLOW_UP
   - "What happened next?" → FOLLOW_UP
   - "Give me an example" → FOLLOW_UP

2. These are STATEMENTS, NOT questions:
   - "Okay" → STATEMENT
   - "That makes sense" → STATEMENT
   - "Interesting" → STATEMENT
   - "Good" → STATEMENT
   - "I understand" → STATEMENT
   - "Let me explain our architecture" → STATEMENT
   - "The position involves AI development" → STATEMENT

3. If the interviewer is explaining something about their company/role, it's a STATEMENT.
4. If the utterance is ambiguous, classify as UNCERTAIN with lower confidence.
5. Detect the question category from the provided list.
6. Determine if the question requires candidate-specific context or general knowledge.

Provide confidence between 0.0 and 1.0."""


class QuestionClassifier:
    """Classifies interviewer utterances for answer routing."""

    async def classify(
        self,
        utterance: str,
        conversation_history: Optional[list[dict]] = None,
        *,
        prefer_speed: bool = False,
    ) -> UtteranceClassification:
        """
        Classify an interviewer utterance.
        Returns classification with type, confidence, and category.
        """
        import time
        start_time = time.time()
        
        raw = utterance.strip()
        remainder = strip_leading_greeting(raw)
        if is_greeting_or_filler(raw) and (
            remainder.casefold() == raw.casefold() or is_greeting_or_filler(remainder)
        ):
            return UtteranceClassification(
                type=UtteranceType.STATEMENT,
                confidence=0.99,
                raw_utterance=utterance,
                latency_ms=(time.time() - start_time) * 1000
            )
        if remainder and remainder.casefold() != raw.casefold():
            utterance = remainder

        # Fast-path: check for obvious acknowledgments
        normalized = utterance.strip().lower().rstrip(".!,?")
        if is_greeting_or_filler(utterance):
            return UtteranceClassification(
                type=UtteranceType.STATEMENT,
                confidence=0.99,
                raw_utterance=utterance,
                latency_ms=(time.time() - start_time) * 1000
            )

        # A self-introduction is a new personal question, never a continuation
        # of the previous technical topic. Keep this deterministic because STT
        # commonly produces variants such as "please speak for yourself".
        if is_introduction_question(utterance):
            return UtteranceClassification(
                type=UtteranceType.QUESTION,
                confidence=0.99,
                normalized_question=utterance.strip(),
                raw_utterance=utterance,
                category=QuestionCategory.INTRODUCTION,
                requires_candidate_context=True,
                is_follow_up=False,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Captured speech that is not a question to the candidate (adverts, TTS
        # demo text, a paragraph being read aloud) must never be answered, and
        # must never be glued to the previous topic as a "follow-up" just because
        # it contains "it" or "this".
        if is_non_question_monologue(utterance):
            return UtteranceClassification(
                type=UtteranceType.STATEMENT,
                confidence=0.95,
                raw_utterance=utterance,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Resolve short/deictic follow-ups locally. Requiring history prevents a
        # standalone request such as "give me an example" from being attached to
        # a topic that does not exist. Must run before the "explain..." question
        # prefix, or "Explain more about the stages it goes through" is treated
        # as a brand-new topic.
        if looks_like_follow_up(utterance, conversation_history):
            needs_cv = is_project_cv_question(utterance)
            return UtteranceClassification(
                type=UtteranceType.FOLLOW_UP,
                confidence=0.99,
                normalized_question=utterance.strip(),
                raw_utterance=utterance,
                category=(
                    QuestionCategory.CV_DEEP_DIVE
                    if needs_cv
                    else QuestionCategory.FOLLOW_UP
                ),
                requires_candidate_context=needs_cv,
                is_follow_up=True,
                follow_up_context=_format_follow_up_context(conversation_history or []),
                latency_ms=(time.time() - start_time) * 1000,
            )

        QUESTION_PREFIXES = (
            "what", "why", "how", "when", "where", "who", "which",
            "tell me", "explain", "describe", "can you", "walk me",
            "ما ", "ماذا", "كيف", "لماذا", "هل", "حدثني", "اشرح", "صف ", "أخبرني",
            "شو", "ايش", "إيش", "ايه", "إيه", "يعني",
            "give me", "would you", "could you", "do you", "are you", "did you",
            "is there", "are there", "was there", "were there", "have you", "has", "had"
        )
        
        # "how Python works" vs "how does Python work?". 
        # A simple prefix check works for most questions, but let's be careful not to classify "I know how python works" as a question.
        # But `normalized.startswith()` already checks if the sentence STARTS with it, so it's safe.
        is_obvious_question = utterance.strip().endswith("?") or any(
            normalized.startswith(prefix) for prefix in QUESTION_PREFIXES
        ) or any(phrase in f"{normalized} " for phrase in QUESTION_PHRASES_ANYWHERE)
        
        if is_obvious_question:
            needs_cv = is_project_cv_question(utterance)
            return UtteranceClassification(
                type=UtteranceType.QUESTION,
                confidence=0.95,
                normalized_question=utterance.strip(),
                raw_utterance=utterance,
                category=(
                    QuestionCategory.PROJECT_MANAGEMENT
                    if needs_cv and not is_ai_ml_question(utterance)
                    else (
                        QuestionCategory.AI_ML
                        if is_ai_ml_question(utterance) and not needs_cv
                        else (
                            QuestionCategory.CV_DEEP_DIVE
                            if needs_cv
                            else None
                        )
                    )
                ),
                requires_candidate_context=needs_cv,
                latency_ms=(time.time() - start_time) * 1000
            )

        # Live coaching: skip the extra LLM round-trip (~2-3s). Heuristics above
        # already catch acknowledgments, introductions, follow-ups, and obvious
        # questions. P2: do NOT fail-open unknown text as QUESTION — that made
        # "Yeah, John." / system chrome trigger SHOW_ANSWER.
        if prefer_speed:
            if has_structural_interview_request(utterance):
                needs_cv = is_project_cv_question(utterance)
                return UtteranceClassification(
                    type=UtteranceType.QUESTION,
                    confidence=0.88,
                    normalized_question=utterance.strip(),
                    raw_utterance=utterance,
                    category=(
                        QuestionCategory.CV_DEEP_DIVE
                        if needs_cv
                        else (
                            QuestionCategory.AI_ML
                            if is_ai_ml_question(utterance)
                            else None
                        )
                    ),
                    requires_candidate_context=needs_cv,
                    latency_ms=(time.time() - start_time) * 1000,
                )
            return UtteranceClassification(
                type=UtteranceType.STATEMENT,
                confidence=0.7,
                raw_utterance=utterance,
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Use LLM for nuanced classification (offline / high-quality path)
        context_str = ""
        if conversation_history:
            recent = conversation_history[-5:]  # Last 5 exchanges
            context_str = "\n".join(
                f"- {entry.get('role', 'unknown')}: {entry.get('text', '')}"
                for entry in recent
            )
            context_str = f"\n## Recent Conversation Context\n{context_str}"

        prompt = f"""Classify this interviewer utterance:

## Utterance
"{utterance}"
{context_str}

Determine:
1. type: QUESTION, STATEMENT, FOLLOW_UP, or UNCERTAIN
2. confidence: 0.0 to 1.0
3. normalized_question: Clean version of the question (if it is one)
4. category: The question category (if applicable)
5. requires_candidate_context: Does this need info from the candidate's CV/profile?
6. is_follow_up: Is this a follow-up to a previous question?"""

        try:
            result = await gemini.classify(
                prompt,
                UtteranceClassification,
                system_instruction=CLASSIFICATION_SYSTEM_PROMPT,
            )
            result.raw_utterance = utterance
            needs_cv = is_project_cv_question(utterance)
            if needs_cv:
                result.requires_candidate_context = True
                if result.category in {None, QuestionCategory.AI_ML, QuestionCategory.TECHNICAL}:
                    result.category = QuestionCategory.CV_DEEP_DIVE
            elif is_ai_ml_question(utterance):
                result.category = QuestionCategory.AI_ML
                result.requires_candidate_context = False
            result.latency_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return UtteranceClassification(
                type=UtteranceType.UNCERTAIN,
                confidence=0.4,
                normalized_question=None,
                raw_utterance=utterance,
                latency_ms=(time.time() - start_time) * 1000
            )

    def determine_action(
        self,
        classification: UtteranceClassification,
        *,
        bank_lexical_hit: bool = False,
    ) -> QuestionAction:
        """Determine what action to take based on classification.

        P2 STATEMENT policy (fail-closed):
          QUESTION / FOLLOW_UP → answer
          ACK / SYSTEM_AUDIO / filler / monologue → stop
          STATEMENT → answer only if clear structural interview request,
                      or (gray only) a light lexical bank hit.
        """
        raw = classification.raw_utterance or ""

        if is_greeting_or_filler(raw) or is_system_audio_or_noise(raw):
            return QuestionAction.LISTEN
        if is_non_question_monologue(raw):
            return QuestionAction.LISTEN

        if classification.type in (UtteranceType.QUESTION, UtteranceType.FOLLOW_UP):
            return QuestionAction.SHOW_ANSWER

        if classification.type == UtteranceType.STATEMENT:
            if has_structural_interview_request(raw):
                return QuestionAction.SHOW_ANSWER
            # Gray STATEMENT only: caller may pass a cheap lexical bank hint.
            if bank_lexical_hit:
                return QuestionAction.SHOW_ANSWER
            return QuestionAction.LISTEN

        if classification.type == UtteranceType.UNCERTAIN:
            if has_structural_interview_request(raw) or bank_lexical_hit:
                return QuestionAction.SHOW_ANSWER
            if classification.confidence < 0.55 or len(raw.split()) < 4:
                return QuestionAction.LISTEN
            return QuestionAction.LISTEN

        return QuestionAction.LISTEN

    def light_lexical_bank_hit(self, utterance: str) -> bool:
        """Cheap lexical bank check for gray STATEMENT — no semantic recovery."""
        text = " ".join((utterance or "").strip().split())
        if not text or is_greeting_or_filler(text) or is_system_audio_or_noise(text):
            return False
        if not has_structural_interview_request(text) and len(text.split()) < 4:
            # Too thin to bother the bank.
            return False
        try:
            from app.services.question_bank import question_bank

            match = question_bank.match(text, tech_repair=False)
        except Exception as exc:
            logger.debug("light lexical bank check skipped: %s", exc)
            return False
        if match is None:
            return False
        # Lexical evidence only — ignore semantic-only promotions.
        return bool(match.lexical >= 0.72 or (match.is_strong and match.lexical >= 0.60))


# Singleton instance
question_classifier = QuestionClassifier()
