import time
import logging
import re

logger = logging.getLogger(__name__)

class TranscriptAggregator:
    """Aggregates STT transcripts into full questions with dedup."""
    def __init__(self, timeout_ms=1000, dedup_window_s=5.0):
        self.buffer = []
        self.timeout_ms = timeout_ms
        self.dedup_window_s = dedup_window_s
        self.last_update_time = time.time()
        self.recent_questions = []
        
    def add_transcript(self, text: str):
        self.buffer.append(text)
        self.last_update_time = time.time()
        
    def get_aggregated(self) -> str:
        return " ".join(self.buffer).strip()
        
    def should_flush(self) -> bool:
        if not self.buffer:
            return False
        elapsed = (time.time() - self.last_update_time) * 1000
        # If it's very short, maybe wait longer? For now just use timeout
        return elapsed >= self.timeout_ms
        
    def clear(self):
        self.buffer.clear()
        
    def is_duplicate(self, text: str) -> bool:
        now = time.time()
        self.recent_questions = [(t, q) for t, q in self.recent_questions if now - t <= self.dedup_window_s]
        
        text_norm = self._normalize(text)
        for t, q in self.recent_questions:
            q_norm = self._normalize(q)
            if not text_norm or not q_norm:
                continue
            if text_norm == q_norm:
                logger.info(f"Duplicate question ignored: '{text_norm}'")
                return True
            # Treat shorter fragment of a longer recent question as echo/dup.
            # Do NOT treat a longer extension as a duplicate — that used to
            # drop the completed question after a short first STT fragment.
            if text_norm in q_norm and len(text_norm) < len(q_norm):
                logger.info(f"Duplicate fragment ignored: '{text_norm}'")
                return True
                
        self.recent_questions.append((now, text))
        return False

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize harmless STT punctuation/casing differences for dedup."""
        return re.sub(r"[^\w\u0600-\u06ff]+", " ", text.casefold()).strip()
