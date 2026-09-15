"""
AI Interview Coach - WebSocket Real-Time Interview Endpoint

Handles live interview sessions with:
- Audio streaming (binary frames)
- State machine events (JSON messages)
- Real-time answer generation
- Latency metrics
"""

from __future__ import annotations
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.session import SessionState, SessionEvent
from app.models.candidate import AnswerLengthMode, AnswerLanguageMode
from app.models.answer import (
    AnswerStrategy,
    ConfidenceScores,
    GeneratedAnswer,
    ValidationResult,
)
from app.services.session_manager import session_manager
from app.services.question_classifier import question_classifier
from app.services.answer_generator import answer_generator
from app.services.candidate_profile import candidate_profile_service
from app.audio.capture_manager import capture_manager
from app.services.live_audio import LiveAudioOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time interview sessions.

    Message types:
    - Binary: Audio frames
    - JSON: Control messages

    Control message format:
    {
        "type": "start" | "pause" | "resume" | "end" | "utterance" | "config",
        "data": { ... }
    }
    """
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if session is None:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    profile = candidate_profile_service.get_profile(session.candidate_id)
    if profile is None:
        await websocket.send_json({"type": "error", "message": "Profile not found"})
        await websocket.close()
        return

    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "state": session.state.value,
        })
    except WebSocketDisconnect:
        logger.info("WebSocket closed before handshake completed: %s", session_id)
        return

    answer_length_mode = profile.interview_preferences.answer_length
    answer_language_mode = profile.interview_preferences.answer_language
    orchestrator: Optional[LiveAudioOrchestrator] = None

    try:
        while True:
            data = await websocket.receive()
            if data.get("type") == "websocket.disconnect":
                logger.info("WebSocket disconnected: %s", session_id)
                break

            if "text" in data:
                # JSON control message
                try:
                    message = json.loads(data["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })
                    continue

                msg_type = message.get("type")

                if msg_type == "config":
                    try:
                        data = message.get("data", {})
                        if data.get("length_mode"):
                            answer_length_mode = AnswerLengthMode(data["length_mode"])
                        if data.get("language_mode"):
                            answer_language_mode = AnswerLanguageMode(data["language_mode"])
                        capture_manager.configure(
                            mic_device_index=data.get("mic_device_index"),
                            loopback_device_index=data.get("loopback_device_index"),
                        )
                        if orchestrator is not None:
                            orchestrator.length_mode = answer_length_mode
                            orchestrator.language_mode = answer_language_mode
                        await websocket.send_json({
                            "type": "config_applied",
                            "status": "success",
                        })
                    except Exception as e:
                        logger.error(f"Failed to configure audio: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Audio config failed: {e}",
                        })

                elif msg_type == "start":
                    try:
                        logger.info("WS start requested for session %s", session_id)
                        if orchestrator is not None and orchestrator.is_running:
                            await websocket.send_json({
                                "type": "info",
                                "message": "Audio session is already running",
                            })
                            continue

                        if session.state == SessionState.IDLE:
                            old, new = session_manager.transition(
                                session_id, SessionEvent.START_SESSION
                            )
                        else:
                            # A browser reconnect can attach to a persisted active
                            # session whose former audio orchestrator no longer exists.
                            session_manager.mark_session_active(session_id)
                            old = new = session.state
                        await websocket.send_json({
                            "type": "state_change",
                            "old_state": old.value,
                            "new_state": new.value,
                        })
                        
                        # Start real-time audio orchestration
                        orchestrator = LiveAudioOrchestrator(
                            websocket,
                            session_id,
                            length_mode=answer_length_mode,
                            language_mode=answer_language_mode,
                        )
                        await orchestrator.start()
                        logger.info("WS live audio started for session %s", session_id)
                        
                    except Exception as e:
                        logger.exception("Failed to start live audio for %s", session_id)
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e),
                        })

                elif msg_type == "pause":
                    try:
                        old, new = session_manager.transition(
                            session_id, SessionEvent.PAUSE_REQUESTED
                        )
                        await websocket.send_json({
                            "type": "state_change",
                            "old_state": old.value,
                            "new_state": new.value,
                        })
                        if orchestrator is not None:
                            await orchestrator.stop()
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e),
                        })

                elif msg_type == "resume":
                    try:
                        old, new = session_manager.transition(
                            session_id, SessionEvent.RESUME_REQUESTED
                        )
                        await websocket.send_json({
                            "type": "state_change",
                            "old_state": old.value,
                            "new_state": new.value,
                        })
                        if orchestrator is not None:
                            await orchestrator.start()
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e),
                        })

                elif msg_type == "end":
                    session_manager.end_session(session_id)
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                    })
                    if orchestrator is not None:
                        await orchestrator.stop()
                        orchestrator = None
                    break

                elif msg_type == "utterance":
                    # Process a transcribed interviewer utterance
                    utterance = message.get("data", {}).get("text", "")
                    if not utterance:
                        continue

                    start_time = time.time()

                    length_mode = AnswerLengthMode(
                        message.get("data", {}).get("length_mode", "STANDARD")
                    )
                    language_mode = AnswerLanguageMode(
                        message.get("data", {}).get(
                            "language_mode", "ANSWER_IN_QUESTION_LANGUAGE"
                        )
                    )

                    # Classify
                    classify_start = time.time()
                    classification = await question_classifier.classify(
                        utterance,
                        conversation_history=session_manager.effective_conversation_history(session),
                    )
                    classify_ms = (time.time() - classify_start) * 1000

                    action = question_classifier.determine_action(classification)

                    await websocket.send_json({
                        "type": "classification",
                        "utterance": utterance,
                        "classification": classification.model_dump(),
                        "action": action.value,
                        "latency_ms": round(classify_ms, 1),
                    })

                    # Generate answer if needed
                    if action.value == "SHOW_ANSWER":
                        await websocket.send_json({
                            "type": "QUESTION_DETECTED",
                            "utterance": utterance,
                        })
                        await websocket.send_json({
                            "type": "ANSWER_GENERATING",
                            "utterance": utterance,
                        })
                        gen_start = time.time()
                        question_id = str(uuid.uuid4())

                        async def on_partial(text: str) -> None:
                            cleaned = (text or "").strip()
                            if len(cleaned) < 4:
                                return
                            draft = GeneratedAnswer(
                                question_id=question_id,
                                question=utterance,
                                normalized_question=classification.normalized_question or utterance,
                                answer_en=cleaned,
                                strategy=AnswerStrategy.TECHNICAL_CONCISE,
                                length_mode=length_mode,
                                confidence=ConfidenceScores(
                                    question_confidence=0.8,
                                    context_confidence=0.7,
                                    answer_confidence=0.7,
                                    technical_confidence=0.7,
                                ),
                                validation=ValidationResult(is_valid=True),
                                action="SHOW_ANSWER",
                            )
                            await websocket.send_json({
                                "type": "ANSWER_PARTIAL",
                                "answer": draft.model_dump(),
                            })

                        generated = await answer_generator.generate(
                            classification=classification,
                            profile=profile,
                            conversation_history=session_manager.effective_conversation_history(session),
                            question_id=question_id,
                            target_role_id=getattr(session, "target_role_id", None),
                            length_mode=length_mode,
                            language_mode=language_mode,
                            prefer_speed=True,
                            on_partial=on_partial,
                        )
                        gen_ms = (time.time() - gen_start) * 1000
                        total_ms = (time.time() - start_time) * 1000

                        await session_manager.record_answer(session_id, generated)

                        await websocket.send_json({
                            "type": "ANSWER_READY",
                            "answer": generated.model_dump(),
                            "metrics": {
                                "classification_ms": round(classify_ms, 1),
                                "generation_ms": round(gen_ms, 1),
                                "total_ms": round(total_ms, 1),
                            },
                        })
                    else:
                        await websocket.send_json({
                            "type": "QUESTION_IGNORED",
                            "utterance": utterance,
                            "reason": action.value,
                        })

                elif msg_type == "candidate_answer":
                    # Record the candidate's actual answer
                    answer_text = message.get("data", {}).get("text", "")
                    question_context = message.get("data", {}).get("question", "")
                    await session_manager.record_candidate_answer(
                        session_id, answer_text, question_context
                    )
                    await websocket.send_json({
                        "type": "candidate_answer_recorded",
                    })

                elif msg_type == "audio_config":
                    # Audio device configuration
                    devices = {
                        "input_devices": [
                            d.__dict__ for d in capture_manager.list_input_devices()
                        ],
                        "loopback_devices": [
                            d.__dict__ for d in capture_manager.list_loopback_devices()
                        ],
                        "output_devices": [
                            d.__dict__ for d in capture_manager.list_output_devices()
                        ],
                    }
                    await websocket.send_json({
                        "type": "audio_devices",
                        "devices": devices,
                    })

                elif msg_type == "get_state":
                    latest = session_manager.get_session(session_id)
                    await websocket.send_json({
                        "type": "state",
                        "state": latest.state.value if latest else "UNKNOWN",
                        "questions_asked": latest.questions_asked if latest else 0,
                    })

                elif msg_type == "force_flush_interviewer":
                    if orchestrator is not None:
                        orchestrator.force_flush_interviewer()
                        await websocket.send_json({
                            "type": "info",
                            "message": "Interviewer buffer force-flushed"
                        })

            elif "bytes" in data:
                # Binary audio frame — future: process through audio pipeline
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass
    finally:
        # Stop capture for this socket only. Do NOT end the interview session —
        # React remounts / brief reconnects would otherwise kill the session
        # before the UI can restart live audio.
        if orchestrator is not None:
            await orchestrator.stop()
