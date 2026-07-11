"""Appointment + Doctor CRUD + PDF ticket generation."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors as _colors

from auth import get_current_user, require_role, optional_user
from models import Appointment, Doctor, User, new_id, utcnow


router = APIRouter(prefix="/api", tags=["clinic"])


def _db(request: Request):
    return request.app.state.db


def _serialize(doc: dict) -> dict:
    """Ensure datetimes go out as ISO strings."""
    if doc is None:
        return doc
    out = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ------------- Doctors -------------
@router.get("/doctors")
async def list_doctors(request: Request):
    docs = await _db(request).doctors.find({}, {"_id": 0}).to_list(200)
    return docs


class DoctorCreate(BaseModel):
    name: str
    specialty: str
    bio: str = ""
    room: Optional[str] = None
    fee: Optional[int] = None
    availability: str = ""
    picture: Optional[str] = None


@router.post("/doctors")
async def create_doctor(body: DoctorCreate, request: Request, admin: User = Depends(require_role("admin"))):
    doc = Doctor(doctor_id=new_id("doc"), **body.model_dump()).model_dump()
    await _db(request).doctors.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ------------- Appointments -------------
class AppointmentCreate(BaseModel):
    doctor_id: str
    patient_name: str
    patient_phone: Optional[str] = None
    starts_at: datetime = Field(..., description="ISO 8601 date-time")
    notes: Optional[str] = None
    source: str = "web"


@router.post("/appointments")
async def create_appointment(
    body: AppointmentCreate,
    request: Request,
    user: Optional[User] = Depends(optional_user),
):
    db = _db(request)
    doc = await db.doctors.find_one({"doctor_id": body.doctor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Doctor not found")

    starts_at = body.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if starts_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Appointment must be in the future")

    appt = Appointment(
        appointment_id=new_id("appt"),
        patient_user_id=user.user_id if user else None,
        patient_name=body.patient_name,
        patient_phone=body.patient_phone,
        doctor_id=doc["doctor_id"],
        doctor_name=doc["name"],
        specialty=doc.get("specialty"),
        starts_at=starts_at,
        notes=body.notes,
        source=body.source,
    ).model_dump()
    await db.appointments.insert_one(appt)

    # Real-time broadcast
    from server import sio  # avoid circular at import time
    await sio.emit(
        "db_update",
        {"operation": "insert", "table": "appointments", "data": _serialize({**appt})},
    )
    appt.pop("_id", None)
    return _serialize(appt)


@router.get("/appointments")
async def list_appointments(
    request: Request,
    user: User = Depends(get_current_user),
    date: Optional[str] = Query(None, description="YYYY-MM-DD filter"),
    doctor_id: Optional[str] = None,
    mine: bool = False,
):
    db = _db(request)
    q: dict = {}

    # Role-based scope
    if user.role == "patient":
        q["patient_user_id"] = user.user_id
    elif user.role == "doctor":
        # doctor sees own
        if user.doctor_id:
            q["doctor_id"] = user.doctor_id
        else:
            # unlinked doctor sees nothing until admin links
            return []

    if mine and user.role == "admin":
        q["patient_user_id"] = user.user_id
    if doctor_id and user.role == "admin":
        q["doctor_id"] = doctor_id

    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD")
        from datetime import timedelta
        q["starts_at"] = {"$gte": day, "$lt": day + timedelta(days=1)}

    docs = await db.appointments.find(q, {"_id": 0}).sort("starts_at", 1).to_list(1000)
    return [_serialize(d) for d in docs]


@router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: str, request: Request, user: User = Depends(get_current_user)):
    doc = await _db(request).appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Appointment not found")
    if user.role == "patient" and doc.get("patient_user_id") != user.user_id:
        raise HTTPException(403, "Forbidden")
    if user.role == "doctor":
        if not user.doctor_id or doc.get("doctor_id") != user.doctor_id:
            raise HTTPException(403, "Forbidden")
    return _serialize(doc)


@router.delete("/appointments/{appointment_id}")
async def cancel_appointment(appointment_id: str, request: Request, user: User = Depends(get_current_user)):
    db = _db(request)
    doc = await db.appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    if user.role == "patient" and doc.get("patient_user_id") != user.user_id:
        raise HTTPException(403, "Forbidden")
    await db.appointments.update_one({"appointment_id": appointment_id}, {"$set": {"status": "cancelled"}})
    from server import sio
    await sio.emit("db_update", {"operation": "update", "table": "appointments", "data": {"appointment_id": appointment_id, "status": "cancelled"}})
    return {"ok": True}


@router.get("/appointments/month/{year}/{month}")
async def appointments_by_month(year: int, month: int, request: Request, user: User = Depends(get_current_user)):
    from datetime import timedelta
    if month < 1 or month > 12:
        raise HTTPException(400, "Invalid month")
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    q = {"starts_at": {"$gte": start, "$lt": end}}
    if user.role == "patient":
        q["patient_user_id"] = user.user_id
    elif user.role == "doctor" and user.doctor_id:
        q["doctor_id"] = user.doctor_id
    docs = await _db(request).appointments.find(q, {"_id": 0}).sort("starts_at", 1).to_list(2000)
    return [_serialize(d) for d in docs]


# ------------- PDF Ticket -------------
def _build_ticket_pdf(appt: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A5, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    forest = HexColor("#0F2C1E")
    terracotta = HexColor("#C8654E")
    sand = HexColor("#F5F0E4")
    muted = HexColor("#6b7d70")

    title = ParagraphStyle("title", parent=styles["Title"], textColor=forest, fontSize=20, leading=24)
    label = ParagraphStyle("lbl", parent=styles["Normal"], textColor=muted, fontSize=8, leading=10, spaceAfter=1)
    value = ParagraphStyle("val", parent=styles["Normal"], textColor=forest, fontSize=13, leading=16, spaceAfter=6)
    mono = ParagraphStyle("mono", parent=styles["Code"], textColor=terracotta, fontSize=12, leading=14)

    starts = appt.get("starts_at")
    if isinstance(starts, str):
        starts_dt = datetime.fromisoformat(starts.replace("Z", "+00:00"))
    else:
        starts_dt = starts

    story = []
    story.append(Paragraph("yuktikAI · Digitix Clinic", title))
    story.append(Paragraph("Appointment Confirmation", ParagraphStyle("sub", parent=styles["Normal"], textColor=terracotta, fontSize=11, spaceAfter=14)))

    data = [
        ["TICKET ID", Paragraph(appt["appointment_id"].upper(), mono)],
        ["PATIENT", appt.get("patient_name", "")],
        ["DOCTOR", appt.get("doctor_name", "")],
        ["SPECIALTY", appt.get("specialty") or ""],
        ["DATE", starts_dt.strftime("%A, %d %B %Y")],
        ["TIME", starts_dt.strftime("%I:%M %p")],
        ["PHONE", appt.get("patient_phone") or "—"],
        ["NOTES", appt.get("notes") or "—"],
    ]
    table = Table(data, colWidths=[35 * mm, 90 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), sand),
        ("TEXTCOLOR", (0, 0), (0, -1), muted),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 0.6, forest),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, sand),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Please arrive 10 minutes before your appointment. Reschedules are free up to 2 hours prior.",
        ParagraphStyle("foot", parent=styles["Normal"], textColor=muted, fontSize=9, leading=12),
    ))
    doc.build(story)
    buf.seek(0)
    return buf.read()


@router.get("/appointments/{appointment_id}/ticket.pdf")
async def download_ticket(appointment_id: str, request: Request, user: User = Depends(get_current_user)):
    doc = await _db(request).appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    if user.role == "patient" and doc.get("patient_user_id") != user.user_id:
        raise HTTPException(403, "Forbidden")
    pdf = _build_ticket_pdf(doc)
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ticket-{appointment_id}.pdf"'},
    )


# ------------- Admin stats -------------
@router.get("/stats")
async def admin_stats(request: Request, admin: User = Depends(require_role("admin"))):
    db = _db(request)
    total_appts = await db.appointments.count_documents({})
    upcoming = await db.appointments.count_documents({"starts_at": {"$gte": datetime.now(timezone.utc)}, "status": "confirmed"})
    total_doctors = await db.doctors.count_documents({})
    total_users = await db.users.count_documents({})
    return {
        "total_appointments": total_appts,
        "upcoming_appointments": upcoming,
        "total_doctors": total_doctors,
        "total_users": total_users,
    }
