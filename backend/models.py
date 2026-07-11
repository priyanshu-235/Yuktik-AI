"""Pydantic models & Mongo helpers for yuktikAI."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Literal
import uuid

from pydantic import BaseModel, Field, EmailStr


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Users / Auth ----------
Role = Literal["patient", "doctor", "admin"]


class User(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    role: Role = "patient"
    doctor_id: Optional[str] = None  # linked doctor profile if role == doctor
    created_at: datetime = Field(default_factory=utcnow)


class SessionRow(BaseModel):
    session_token: str
    user_id: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)


# ---------- Clinic entities ----------
class Doctor(BaseModel):
    doctor_id: str
    name: str
    specialty: str
    bio: str = ""
    room: Optional[str] = None
    fee: Optional[int] = None
    availability: str = ""  # human readable
    picture: Optional[str] = None


class Appointment(BaseModel):
    appointment_id: str
    patient_user_id: Optional[str] = None  # user who booked; may be None for phone
    patient_name: str
    patient_phone: Optional[str] = None
    doctor_id: str
    doctor_name: str
    specialty: Optional[str] = None
    starts_at: datetime  # ISO stored as datetime
    notes: Optional[str] = None
    status: Literal["confirmed", "cancelled", "completed"] = "confirmed"
    source: Literal["voice", "web"] = "voice"
    created_at: datetime = Field(default_factory=utcnow)


# ---------- Voice / chat session ----------
class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    at: datetime = Field(default_factory=utcnow)


class VoiceSession(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    started_at: datetime = Field(default_factory=utcnow)
    turns: List[Turn] = Field(default_factory=list)
    language: Optional[str] = None
    ticket_appointment_id: Optional[str] = None
