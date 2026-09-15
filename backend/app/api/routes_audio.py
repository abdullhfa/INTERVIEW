"""
AI Interview Coach - Audio devices + automated interview audio Test Runner API
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.audio.capture_manager import capture_manager
from app.services import interview_audio_runner as runner

router = APIRouter()


class AudioDeviceResponse(BaseModel):
    index: int
    name: str
    channels: int
    sample_rate: float
    is_input: bool
    is_loopback: bool
    host_api: str
    is_default: bool = False


class AudioDevicesList(BaseModel):
    microphones: List[AudioDeviceResponse]
    loopbacks: List[AudioDeviceResponse]


@router.get("/devices", response_model=AudioDevicesList)
async def get_audio_devices():
    """Get available microphone and loopback audio devices."""
    capture_manager.refresh_devices()
    mics = capture_manager.list_input_devices()
    loopbacks = capture_manager.list_loopback_devices()

    return AudioDevicesList(
        microphones=[
            AudioDeviceResponse(
                index=d.index,
                name=d.name,
                channels=d.channels,
                sample_rate=d.sample_rate,
                is_input=d.is_input,
                is_loopback=d.is_loopback,
                host_api=d.host_api,
                is_default=d.is_default,
            )
            for d in mics
        ],
        loopbacks=[
            AudioDeviceResponse(
                index=d.index,
                name=d.name,
                channels=d.channels,
                sample_rate=d.sample_rate,
                is_input=d.is_input,
                is_loopback=d.is_loopback,
                host_api=d.host_api,
                is_default=d.is_default,
            )
            for d in loopbacks
        ],
    )


class EvaluateClipRequest(BaseModel):
    file: str = Field(..., description="Relative path under stress-pilot, e.g. audio/Q156_....wav")


class StressReportRequest(BaseModel):
    question_id: Optional[int] = None
    speaker: Optional[str] = None
    condition: Optional[str] = None
    limit: int = Field(12, ge=1, le=180)


@router.post("/evaluate-stress-clip")
async def evaluate_stress_clip(payload: EvaluateClipRequest) -> dict[str, Any]:
    """Direct-inject one WAV into STT → intent → answer and return graded result."""
    try:
        metadata = runner.load_metadata()
        meta = runner.find_meta_for_file(payload.file, metadata)
        if meta is None:
            meta = {
                "file": payload.file,
                "main_question": "",
                "spoken_wording": "",
                "expected_answer": None,
            }
        else:
            meta = dict(meta)
            meta["file"] = payload.file
        result = await runner.run_one(meta)
        return runner._result_to_dict(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/stress-report")
@router.post("/run-audio-tests")
async def run_audio_tests(payload: StressReportRequest) -> dict[str, Any]:
    """
    Automated Test Runner (Direct Audio Injection).

    Runs filtered stress-pilot clips end-to-end and writes:
    - INTERVIEW_AUDIO_TEST_REPORT.html
    - INTERVIEW_AUDIO_TEST_REPORT.json
    """
    try:
        return await runner.run_suite(
            question_id=payload.question_id,
            speaker=payload.speaker,
            condition=payload.condition,
            limit=payload.limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/latest-report")
async def latest_report():
    """Serve the latest HTML stress-test report."""
    path = runner.REPORTS_DIR / "INTERVIEW_AUDIO_TEST_REPORT.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No report generated yet")
    return FileResponse(path, media_type="text/html")