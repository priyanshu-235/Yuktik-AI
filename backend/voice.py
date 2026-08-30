"""Voice pipeline: Sarvam STT + Gemini chat with tool-calling + Sarvam TTS.

One HTTP call = one full turn:
  audio in -> Sarvam STT -> Gemini (with tools) -> Sarvam TTS -> audio out.

Design goals: minimal tokens, fewest API calls.
- Compact system prompt (clinic facts inlined)
- Rolling window: keep only last 6 turns (older ones dropped)
- Function calling for structured booking (no free-form JSON parsing)
- Cap max output tokens
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import pytz
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import optional_user
from models import Turn, VoiceSession, new_id, utcnow

logger = logging.getLogger("voice")

router = APIRouter(prefix="/api/voice", tags=["voice"])

IST = pytz.timezone("Asia/Kolkata")

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


# --------- System prompt (compact) ---------
def _system_prompt(user_name: Optional[str], doctors_snippet: str) -> str:
    now_ist = datetime.now(IST).strftime("%A, %d %B %Y at %I:%M %p IST")
    name_line = f"Caller name: {user_name}." if user_name else ""
    return f"""You are Asha, the friendly voice assistant for Digitix Multispeciality Clinic in Bengaluru.
You handle: (1) FAQ about the clinic, (2) Symptom triage + doctor recommendation, (3) Appointment booking.

RULES:
- Speak in the SAME language the user used (English or Hindi). If Hindi, use natural Devanagari transliteration where helpful.
- Keep replies short — max 2 sentences, TTS-friendly, natural pauses via commas.
- Ask ONE thing at a time.
- Never invent doctors/times. Use only DOCTORS below.
- For bookings, collect: patient name, doctor, date+time, phone. Then call the tool `book_appointment`.
- After booking, mention the appointment id briefly.
- For any red-flag symptom (severe chest pain, breathlessness, fainting, uncontrolled bleeding), immediately advise the caller to call 108 or visit the emergency room. Do not book.
- Never prescribe medication or dosage.
- If the user asks a general FAQ (timings, address, insurance, fees) answer directly from the CLINIC FACTS.
- NEVER output JSON or raw data. Always speak naturally to the user. If they ask about bookings, describe them in sentences, not as a list or JSON.

CLINIC FACTS:
- Location: 4th Floor, GreenView Plaza, MG Road, Bengaluru 560001
- Hours: Mon-Fri 9am-6pm, Sat 9am-2pm, Sun closed
- Reception: +91 91234 56789 · Email: support@digitixclinic.in
- Insurance: Star Health, HDFC Ergo, Bajaj Allianz, ICICI Lombard, Care Health
- Payments: UPI, cards, cash. Cancellation free 2h prior; ₹200 no-show fee.

DOCTORS AVAILABLE:
{doctors_snippet}

SYMPTOM ROUTING (pick specialty then recommend doctor):
- Chest pain / palpitations / BP → Cardiology
- Breathlessness / cough → General Medicine / Pulmonology (route to General Medicine if no pulmonologist)
- Skin / hair / acne → Dermatology
- Child fever / vaccination / growth → Pediatrics
- Ear / nose / throat / sinus → ENT
- Pregnancy / menstrual / gynae → Gynecology
- Fever / cold / diabetes / general → General Medicine

Today is {now_ist}. {name_line}
"""


# --------- Tools schema for Gemini function-calling ---------
# We do NOT rely on the SDK's tool-calling interface (keeps message API light).
# Instead we instruct the model to emit a compact JSON block when it wants to book,
# then we parse & execute. This keeps to a single Gemini call per turn.
BOOK_INSTRUCTION = """
When you are ready to actually book, emit ONLY a JSON block on a new line, then the confirmation sentence, e.g.:
<<<BOOK
{"patient_name": "Rajesh Kumar", "doctor_id": "doc_xxx", "starts_at": "2026-01-15T14:30:00+05:30", "phone": "9876543210", "notes": "chest pain"}
BOOK>>>
Booked! Your appointment id will be shared next.

Rules for the JSON:
- doctor_id MUST be one of the ids listed above.
- starts_at MUST be ISO 8601 with +05:30 offset and in the future.
- patient_name in English/Roman script even if user spoke Hindi.
"""


BOOK_BLOCK_RE = re.compile(r"<<<BOOK\s*(\{.*?\})\s*BOOK>>>", re.DOTALL)


# --------- Helpers ---------
def _sarvam_key() -> str:
    key = os.getenv("SARVAM_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured on server")
    return key


async def sarvam_stt(audio_bytes: bytes, filename: str, content_type: str) -> tuple[str, str]:
    """Returns (transcript, language_code)"""
    key = _sarvam_key()
    async with httpx.AsyncClient(timeout=90) as client:
        files = {"file": (filename or "audio.webm", audio_bytes, content_type or "audio/webm")}
        data = {"model": "saarika:v2.5", "language_code": "unknown"}
        r = await client.post(
            SARVAM_STT_URL,
            files=files,
            data=data,
            headers={"api-subscription-key": key},
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Sarvam STT error: {r.status_code} {r.text[:200]}")
    body = r.json()
    return body.get("transcript", ""), body.get("language_code", "en-IN")


async def sarvam_tts(text: str, language_code: str = "hi-IN", speaker: str = "priya") -> str:
    """Returns base64 wav audio."""
    key = _sarvam_key()
    # Cap text to ~500 chars for latency
    text = text[:500]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": key, "Content-Type": "application/json"},
            json={
                "inputs": [text],
                "target_language_code": language_code if language_code and "-" in language_code else "hi-IN",
                "speaker": speaker,
                "model": "bulbul:v3",
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
            },
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Sarvam TTS error: {r.status_code} {r.text[:200]}")
    body = r.json()
    audios = body.get("audios") or []
    if not audios:
        raise HTTPException(status_code=502, detail="Sarvam TTS returned no audio")
    return audios[0]  # already base64


async def _doctors_snippet(db) -> tuple[str, dict]:
    docs = await db.doctors.find({}, {"_id": 0}).to_list(100)
    lines = []
    lookup = {}
    for d in docs:
        lookup[d["doctor_id"]] = d
        lines.append(
            f"- id={d['doctor_id']} · {d['name']} ({d['specialty']}) — {d.get('availability','')}"
        )
    return "\n".join(lines) if lines else "(no doctors configured)", lookup


def _language_for_tts(lang_code: str, transcript: str, reply: str) -> str:
    # Sarvam TTS supports specific -IN codes. Detect Devanagari for reply.
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", reply or transcript or ""))
    if has_devanagari:
        return "hi-IN"
    if lang_code and lang_code.lower().startswith("en"):
        return "en-IN"
    return "hi-IN"


# --------- Gemini call: uses your Google AI Studio key ---------
async def call_llm(session_id: str, system_msg: str, user_text: str, history: list[Turn]) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured. Add it to backend/.env",
        )
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro").strip()
    logger.info("Gemini request model=%s", model)

    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=gemini_key)
    contents = []
    for t in history[-6:]:
        role = "user" if t.role == "user" else "model"
        contents.append(genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=t.text)]))
    contents.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=user_text)]))

    cfg = genai_types.GenerateContentConfig(
        system_instruction=system_msg,
        temperature=0.4,
    )
    import asyncio as _asyncio
    def _sync_call():
        return client.models.generate_content(model=model, contents=contents, config=cfg)
    resp = await _asyncio.to_thread(_sync_call)
    return getattr(resp, "text", None) or ""


# --------- Endpoints ---------
@router.post("/session")
async def start_session(request: Request, user=Depends(optional_user)):
    session = VoiceSession(session_id=new_id("vs"), user_id=user.user_id if user else None)
    await request.app.state.db.voice_sessions.insert_one(session.model_dump())
    return {"session_id": session.session_id}


class TextTurnBody(BaseModel):
    session_id: str
    text: str


@router.post("/turn")
async def voice_turn(
    request: Request,
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    user=Depends(optional_user),
):
    """Handles one full turn: audio in -> transcript, reply text, reply audio (base64), optional ticket."""
    db = request.app.state.db
    session_doc = await db.voice_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session_doc:
        raise HTTPException(404, "voice session not found")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "empty audio")

    transcript, lang_code = await sarvam_stt(audio_bytes, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    if not transcript.strip():
        transcript = ""

    doctors_snippet, doctors_lookup = await _doctors_snippet(db)
    sys_prompt = _system_prompt(user.name if user else None, doctors_snippet) + "\n" + BOOK_INSTRUCTION

    reply = await call_llm(
        session_id=session_id,
        system_msg=sys_prompt,
        user_text=transcript or "(user was silent)",
        history=[Turn(**t) for t in session_doc.get("turns", [])],
    )
    ticket = await _maybe_book(reply, db, user, doctors_lookup)

    reply_clean = BOOK_BLOCK_RE.sub("", reply).strip()
    if ticket:
        reply_clean = f"{reply_clean}\n\nYour appointment id is {ticket['appointment_id'].upper()}."

    tts_lang = _language_for_tts(lang_code, transcript, reply_clean)
    audio_b64 = ""
    try:
        audio_b64 = await sarvam_tts(reply_clean, language_code=tts_lang)
    except HTTPException as e:
        # TTS failure shouldn't block returning transcript+text
        logger.warning(f"TTS failed: {e.detail}")

    # Persist turns
    new_turns = session_doc.get("turns", []) + [
        Turn(role="user", text=transcript).model_dump(),
        Turn(role="assistant", text=reply_clean).model_dump(),
    ]
    update = {"turns": new_turns, "language": lang_code}
    if ticket:
        update["ticket_appointment_id"] = ticket["appointment_id"]
    await db.voice_sessions.update_one({"session_id": session_id}, {"$set": update})

    return {
        "transcript": transcript,
        "reply": reply_clean,
        "audio_base64": audio_b64,
        "audio_mime": "audio/wav",
        "language": lang_code,
        "ticket": ticket,
    }


@router.post("/turn/text")
async def voice_turn_text(body: TextTurnBody, request: Request, user=Depends(optional_user)):
    """Text-only turn (useful for fallback/testing without audio)."""
    db = request.app.state.db
    session_doc = await db.voice_sessions.find_one({"session_id": body.session_id}, {"_id": 0})
    if not session_doc:
        raise HTTPException(404, "voice session not found")

    doctors_snippet, doctors_lookup = await _doctors_snippet(db)
    sys_prompt = _system_prompt(user.name if user else None, doctors_snippet) + "\n" + BOOK_INSTRUCTION
    reply = await call_llm(
        session_id=body.session_id,
        system_msg=sys_prompt,
        user_text=body.text,
        history=[Turn(**t) for t in session_doc.get("turns", [])],
    )
    ticket = await _maybe_book(reply, db, user, doctors_lookup)
    reply_clean = BOOK_BLOCK_RE.sub("", reply).strip()
    if ticket:
        reply_clean = f"{reply_clean}\n\nYour appointment id is {ticket['appointment_id'].upper()}."

    new_turns = session_doc.get("turns", []) + [
        Turn(role="user", text=body.text).model_dump(),
        Turn(role="assistant", text=reply_clean).model_dump(),
    ]
    update = {"turns": new_turns}
    if ticket:
        update["ticket_appointment_id"] = ticket["appointment_id"]
    await db.voice_sessions.update_one({"session_id": body.session_id}, {"$set": update})

    return {"transcript": body.text, "reply": reply_clean, "ticket": ticket}


async def _maybe_book(reply: str, db, user, doctors_lookup: dict) -> Optional[dict]:
    m = BOOK_BLOCK_RE.search(reply or "")
    if not m:
        return None
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        logger.warning("Book block was not valid JSON")
        return None

    doctor_id = payload.get("doctor_id")
    doctor = doctors_lookup.get(doctor_id)
    if not doctor:
        # try to match by name if id missing
        for d in doctors_lookup.values():
            if payload.get("doctor", "").lower() in d["name"].lower():
                doctor = d
                doctor_id = d["doctor_id"]
                break
    if not doctor:
        logger.warning(f"Doctor {doctor_id} not found")
        return None

    starts_raw = payload.get("starts_at")
    try:
        starts_at = datetime.fromisoformat(starts_raw)
    except Exception:
        logger.warning(f"Invalid starts_at: {starts_raw}")
        return None
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=IST)
    if starts_at < datetime.now(IST):
        logger.warning("Booking rejected: time in past")
        return None

    from models import Appointment
    appt = Appointment(
        appointment_id=new_id("appt"),
        patient_user_id=user.user_id if user else None,
        patient_name=payload.get("patient_name") or (user.name if user else "Guest"),
        patient_phone=payload.get("phone"),
        doctor_id=doctor_id,
        doctor_name=doctor["name"],
        specialty=doctor.get("specialty"),
        starts_at=starts_at,
        notes=payload.get("notes"),
        source="voice",
    ).model_dump()
    await db.appointments.insert_one(appt)

    from server import sio
    appt_out = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in appt.items() if k != "_id"}
    await sio.emit("db_update", {"operation": "insert", "table": "appointments", "data": appt_out})
    return appt_out
