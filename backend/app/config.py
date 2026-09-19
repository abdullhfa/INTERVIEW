
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = Field(..., description="DeepSeek API key")
    deepseek_base_url: str = Field(
        "https://api.deepseek.com",
        description="DeepSeek OpenAI-compatible API base URL",
    )
    deepseek_model: str = Field(
        "deepseek-v4-flash",
        description="Default DeepSeek model for answers, CV extraction, and classification",
    )

    # Optional: only used for audio STT fallback when Google Web Speech fails
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Optional Gemini key for audio transcription fallback only",
    )
    gemini_fast_model: str = Field(
        "gemini-2.0-flash",
        description="Gemini model for optional audio STT fallback",
    )
    gemini_stt_model: str = Field(
        "gemini-2.0-flash",
        description="Primary Gemini model for optional live audio STT fallback",
    )

    # Legacy setting names — all map to deepseek_model
    @property
    def gemini_reasoning_model(self) -> str:
        return self.deepseek_model

    @property
    def gemini_answer_model(self) -> str:
        return self.deepseek_model

    @property
    def gemini_cv_model(self) -> str:
        return self.deepseek_model

    @property
    def gemini_live_model(self) -> str:
        return self.deepseek_model

    llm_request_timeout_seconds: float = Field(
        45.0, description="Maximum time allowed for one DeepSeek answer request"
    )
    gemini_cv_request_timeout_seconds: float = Field(
        90.0,
        description="Maximum time for CV extraction attempt",
    )
    cv_max_input_chars: int = Field(
        120_000,
        description="Maximum CV characters sent to Gemini for profile extraction",
    )
    cv_max_output_tokens: int = Field(
        16384,
        description="Maximum output tokens for structured CV extraction",
    )
    cv_fast_input_chars: int = Field(
        10_000,
        description="Character limit for the fast CV extraction pass",
    )
    cv_fast_output_tokens: int = Field(
        3072,
        description="Output token budget for fast CV extraction",
    )
    cv_fast_timeout_seconds: float = Field(
        35.0,
        description="Timeout for the fast CV extraction pass",
    )

    database_url: str = Field(
        "sqlite+aiosqlite:///./interview_coach.db",
        description="SQLAlchemy database URL",
    )

    audio_sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    audio_channels: int = Field(1, description="Audio channels (mono)")
    audio_chunk_ms: int = Field(32, description="Audio chunk size in milliseconds")
    vad_threshold: float = Field(0.5, description="VAD activation threshold")
    vad_min_speech_ms: int = Field(
        64,
        description=(
            "Minimum speech duration to confirm speech_start (~1–2 frames at 32ms). "
            "Keep low: actual utterance audio starts from the pre-roll buffer, not VAD crop."
        ),
    )
    vad_min_silence_ms: int = Field(
        600, description="Minimum silence to finalize candidate utterance"
    )
    vad_interviewer_min_silence_ms: int = Field(
        550,
        description=(
            "Minimum silence before finalizing interviewer speech. "
            "550ms for live latency (was 900); raise if questions get cut mid-sentence."
        ),
    )
    vad_pre_roll_ms: int = Field(
        450,
        description=(
            "Circular loopback pre-roll kept before VAD speech_start. "
            "Whisper receives pre-roll + speech (not a VAD-cropped onset). "
            "450ms trims decode audio vs 600 while keeping onset margin."
        ),
    )
    vad_post_roll_ms: int = Field(
        120,
        description="Extra audio kept after VAD end-of-speech before flushing to STT",
    )
    interviewer_stt_merge_ms: int = Field(
        0,
        description=(
            "Extra wait to merge transcript fragments after STT. "
            "Keep 0 for fast answers; rely on vad_interviewer_min_silence_ms instead."
        ),
    )
    stt_timeout_seconds: float = Field(
        6.0,
        description="Maximum time for one interviewer STT attempt (Whisper first).",
    )
    stt_retry_timeout_seconds: float = Field(
        4.0,
        description="Timeout for the single automatic STT retry after timeout/empty",
    )
    stt_languages: str = Field(
        "ar-SA,en-US",
        description="Comma-separated Google STT language codes tried sequentially as fallback",
    )
    question_bank_enabled: bool = Field(
        True,
        description="Answer instantly from the prepared question bank when the match is strong",
    )
    whisper_stt_enabled: bool = Field(
        True,
        description="Use local faster-whisper as the primary live STT engine",
    )
    whisper_model_size: str = Field(
        "distil-large-v3",
        description=(
            "faster-whisper model. distil-large-v3 on GPU is accent-robust (~1s per question); "
            "falls back to whisper_fallback_model_size on CPU when CUDA is unavailable."
        ),
    )
    whisper_device: str = Field(
        "auto",
        description="Whisper device: auto (cuda if available, else cpu), cuda, or cpu",
    )
    whisper_compute_type: str = Field(
        "auto",
        description="Whisper compute type: auto (int8_float16 on cuda, int8 on cpu) or explicit value",
    )
    whisper_language: str = Field(
        "en",
        description="Force Whisper decoding language (interview questions are English only). Empty = auto-detect.",
    )
    whisper_beam_size: int = Field(
        1,
        description=(
            "Beam size for first-pass Whisper. 1 for live latency; "
            "accurate second-pass may still widen beam slightly. best_of stays 1."
        ),
    )
    whisper_fallback_model_size: str = Field(
        "base",
        description="CPU fallback model when the GPU model cannot be loaded",
    )
    whisper_stt_timeout_seconds: float = Field(
        8.0,
        description="Maximum time for one local Whisper transcription",
    )
    google_stt_fallback_enabled: bool = Field(
        False,
        description="Use Google Web Speech when Whisper returns empty (often slow/blocked)",
    )
    google_stt_per_lang_timeout_seconds: float = Field(
        3.0,
        description="Per-language timeout when Google Web Speech is used as fallback",
    )
    google_stt_timeout_seconds: float = Field(
        2.0,
        description="Short timeout for Google Web Speech before Gemini audio fallback",
    )
    candidate_stt_timeout_seconds: float = Field(
        3.0,
        description="Short STT timeout for candidate audio so it cannot block coaching",
    )
    gemini_request_timeout_seconds: float = Field(
        18.0, description="Timeout for live answer generation requests"
    )
    gemini_long_request_timeout_seconds: float = Field(
        120.0,
        description="Maximum time allowed for long LLM tasks such as CV extraction",
    )
    primary_language: str = Field(
        "en-US", description="Primary language for STT"
    )

    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    cors_origins: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175",
        description="Allowed CORS origins",
    )

    session_expiry_hours: int = Field(24, description="Session expiry in hours")
    max_upload_size_mb: int = Field(50, description="Max upload size in MB")

    upload_dir: str = Field("./uploads", description="Directory for uploaded files")
    chroma_dir: str = Field("./chroma_db", description="ChromaDB persistence directory")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def audio_chunk_samples(self) -> int:
        """Number of samples per audio chunk."""
        return int(self.audio_sample_rate * self.audio_chunk_ms / 1000)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


def get_settings() -> Settings:
    """Load settings from environment / .env (values are not constructor args)."""
    return Settings()  # pyright: ignore[reportCallIssue]


settings = get_settings()
