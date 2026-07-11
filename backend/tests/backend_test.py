"""Backend regression suite for yuktikAI (iteration 2).

Covers native Google OAuth refactor + direct Gemini refactor.
- /api/auth/google (replaces /api/auth/session): expects 503 when GOOGLE_CLIENT_ID empty
- /api/auth/config public endpoint
- /api/auth/logout: revokes bearer session
- Voice: /voice/turn/text -> 503 (GEMINI_API_KEY empty), /voice/turn -> 503 (SARVAM empty)
- Appointments RBAC, PDF, cancel, month
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path("/app/frontend/.env"))
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"Authorization": "Bearer sess_admin"}
DOC = {"Authorization": "Bearer sess_doc"}
PAT = {"Authorization": "Bearer sess_pat"}

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture(scope="module")
def created_ids():
    return {"appts": [], "doctors": []}


# ---------------- Health ----------------
def test_health():
    r = requests.get(f"{API}/health", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"


# ---------------- Doctors ----------------
def test_list_doctors_seeded():
    r = requests.get(f"{API}/doctors", timeout=15)
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list)
    assert len(docs) >= 6
    names = {d["name"] for d in docs}
    expected = {
        "Dr. Aneeta Rao", "Dr. Sameer Kulkarni", "Dr. Neha Sharma",
        "Dr. Ravi Iyer", "Dr. Priya Menon", "Dr. Arvind Deshmukh",
    }
    assert expected.issubset(names), f"Missing seeded doctors: {expected - names}"


@pytest.fixture(scope="module")
def aneeta_id():
    r = requests.get(f"{API}/doctors", timeout=15)
    return next(d["doctor_id"] for d in r.json() if d["name"] == "Dr. Aneeta Rao")


# ---------------- Auth: native Google OAuth ----------------
def test_auth_config_when_client_id_empty():
    r = requests.get(f"{API}/auth/config", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["google_client_id"] == ""
    assert j["configured"] is False


def test_google_login_without_client_id_returns_503():
    r = requests.post(f"{API}/auth/google", json={"credential": "fake-token"}, timeout=15)
    assert r.status_code == 503, r.text
    assert "GOOGLE_CLIENT_ID" in r.text


def test_me_without_token_401():
    r = requests.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 401


def test_me_patient():
    r = requests.get(f"{API}/auth/me", headers=PAT, timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["role"] == "patient"
    assert j["user_id"] == "user_pat1"


def test_me_admin():
    r = requests.get(f"{API}/auth/me", headers=ADMIN, timeout=10)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_me_doctor_linked():
    r = requests.get(f"{API}/auth/me", headers=DOC, timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["role"] == "doctor"
    assert j.get("doctor_id")


def test_logout_revokes_session_then_reseed():
    """Create a throwaway session token in Mongo, hit /logout, verify /me 401."""
    import pymongo
    from pymongo import MongoClient
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "yuktik_ai")]
    tok = "sess_test_logout_temp"
    db.user_sessions.delete_many({"session_token": tok})
    db.user_sessions.insert_one({
        "user_id": "user_pat1",
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    hdr = {"Authorization": f"Bearer {tok}"}
    r = requests.get(f"{API}/auth/me", headers=hdr, timeout=10)
    assert r.status_code == 200

    r = requests.post(f"{API}/auth/logout", headers=hdr, timeout=10)
    assert r.status_code == 200
    assert r.json().get("ok") is True

    r = requests.get(f"{API}/auth/me", headers=hdr, timeout=10)
    assert r.status_code == 401
    client.close()


# ---------------- Role gating ----------------
def test_users_list_forbidden_for_patient():
    r = requests.get(f"{API}/auth/users", headers=PAT, timeout=10)
    assert r.status_code == 403


def test_users_list_admin_ok():
    r = requests.get(f"{API}/auth/users", headers=ADMIN, timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list) and len(r.json()) >= 3


def test_admin_set_role_patient():
    r = requests.post(
        f"{API}/auth/users/user_pat1/role",
        headers=ADMIN,
        json={"role": "patient"},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_set_role_doctor_with_id(aneeta_id):
    """Admin sets user_doc1 as doctor linked to Aneeta (idempotent reseed)."""
    r = requests.post(
        f"{API}/auth/users/user_doc1/role",
        headers=ADMIN,
        json={"role": "doctor", "doctor_id": aneeta_id},
        timeout=10,
    )
    assert r.status_code == 200
    # Verify via /me
    r = requests.get(f"{API}/auth/me", headers=DOC, timeout=10)
    assert r.status_code == 200
    assert r.json().get("doctor_id") == aneeta_id


# ---------------- Voice session + LLM 503 ----------------
@pytest.fixture(scope="module")
def voice_session_id():
    r = requests.post(f"{API}/voice/session", headers=PAT, timeout=15)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    assert sid.startswith("vs_")
    return sid


def test_voice_text_turn_no_gemini_key_503(voice_session_id):
    r = requests.post(
        f"{API}/voice/turn/text",
        headers=PAT,
        json={"session_id": voice_session_id, "text": "hello"},
        timeout=30,
    )
    assert r.status_code == 503, r.text
    assert "GEMINI_API_KEY" in r.text


def test_voice_audio_endpoint_sarvam_missing_503(voice_session_id):
    files = {"audio": ("a.webm", b"fakebytes", "audio/webm")}
    data = {"session_id": voice_session_id}
    r = requests.post(f"{API}/voice/turn", headers=PAT, data=data, files=files, timeout=30)
    assert r.status_code == 503
    assert "SARVAM_API_KEY" in r.text or "sarvam" in r.text.lower()


# ---------------- Web appointment creation ----------------
@pytest.fixture(scope="module")
def web_appt_id(aneeta_id, created_ids):
    starts = (datetime.now(timezone.utc) + timedelta(days=5, hours=2)).isoformat()
    payload = {
        "doctor_id": aneeta_id,
        "patient_name": "TEST_WebPatient",
        "patient_phone": "9998887777",
        "starts_at": starts,
    }
    r = requests.post(f"{API}/appointments", headers=PAT, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    aid = r.json()["appointment_id"]
    created_ids["appts"].append(aid)
    return aid


def test_web_booking_creates_and_persists(web_appt_id):
    r = requests.get(f"{API}/appointments/{web_appt_id}", headers=PAT, timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["patient_name"] == "TEST_WebPatient"
    assert j["source"] == "web"
    assert j["patient_user_id"] == "user_pat1"


def test_past_appointment_rejected(aneeta_id):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = requests.post(
        f"{API}/appointments", headers=PAT,
        json={"doctor_id": aneeta_id, "patient_name": "TEST_PastP", "starts_at": past},
        timeout=15,
    )
    assert r.status_code == 400


def test_create_appt_unknown_doctor():
    starts = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    r = requests.post(
        f"{API}/appointments", headers=PAT,
        json={"doctor_id": "doc_nonexistent", "patient_name": "X", "starts_at": starts},
        timeout=15,
    )
    assert r.status_code == 404


# ---------------- Role-scoped listings ----------------
def test_list_appts_as_patient(web_appt_id):
    r = requests.get(f"{API}/appointments", headers=PAT, timeout=15)
    assert r.status_code == 200
    docs = r.json()
    ids = {d["appointment_id"] for d in docs}
    assert web_appt_id in ids
    for d in docs:
        assert d["patient_user_id"] == "user_pat1"


def test_list_appts_as_doctor():
    r = requests.get(f"{API}/appointments", headers=DOC, timeout=15)
    assert r.status_code == 200
    me = requests.get(f"{API}/auth/me", headers=DOC, timeout=10).json()
    for d in r.json():
        assert d["doctor_id"] == me["doctor_id"]


def test_list_appts_as_admin_all(web_appt_id):
    r = requests.get(f"{API}/appointments", headers=ADMIN, timeout=15)
    assert r.status_code == 200
    ids = {d["appointment_id"] for d in r.json()}
    assert web_appt_id in ids


def test_get_appt_doctor_linked_ok(web_appt_id):
    # sess_doc is linked to Aneeta, appt is with Aneeta -> 200
    r = requests.get(f"{API}/appointments/{web_appt_id}", headers=DOC, timeout=10)
    assert r.status_code == 200


def test_get_appt_unlinked_doctor_403(web_appt_id):
    """Temporarily unlink sess_doc's doctor_id and verify GET /appointments/{id} returns 403."""
    from pymongo import MongoClient
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "yuktik_ai")]
    original = db.users.find_one({"user_id": "user_doc1"}, {"_id": 0})
    original_doctor_id = original.get("doctor_id") if original else None
    try:
        db.users.update_one({"user_id": "user_doc1"}, {"$set": {"doctor_id": None}})
        r = requests.get(f"{API}/appointments/{web_appt_id}", headers=DOC, timeout=10)
        assert r.status_code == 403, r.text
    finally:
        db.users.update_one({"user_id": "user_doc1"}, {"$set": {"doctor_id": original_doctor_id}})
        client.close()


def test_ticket_pdf_download(web_appt_id):
    r = requests.get(f"{API}/appointments/{web_appt_id}/ticket.pdf", headers=PAT, timeout=20)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 500


def test_cancel_appointment_owner(aneeta_id, created_ids):
    starts = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    r = requests.post(f"{API}/appointments", headers=PAT,
                     json={"doctor_id": aneeta_id, "patient_name": "TEST_ToCancel", "starts_at": starts}, timeout=15)
    assert r.status_code == 200
    aid = r.json()["appointment_id"]
    created_ids["appts"].append(aid)

    r = requests.delete(f"{API}/appointments/{aid}", headers=PAT, timeout=15)
    assert r.status_code == 200

    r = requests.get(f"{API}/appointments/{aid}", headers=PAT, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_appts_by_month(web_appt_id):
    r = requests.get(f"{API}/appointments/{web_appt_id}", headers=PAT, timeout=10)
    starts = r.json()["starts_at"]
    dt = datetime.fromisoformat(starts.replace("Z", "+00:00"))
    r = requests.get(f"{API}/appointments/month/{dt.year}/{dt.month}", headers=PAT, timeout=15)
    assert r.status_code == 200
    ids = {d["appointment_id"] for d in r.json()}
    assert web_appt_id in ids


def test_month_invalid():
    r = requests.get(f"{API}/appointments/month/2026/13", headers=PAT, timeout=10)
    assert r.status_code == 400


def test_month_2026_7_ok():
    r = requests.get(f"{API}/appointments/month/2026/7", headers=PAT, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------- Admin stats ----------------
def test_stats_admin_only():
    r = requests.get(f"{API}/stats", headers=PAT, timeout=10)
    assert r.status_code == 403
    r = requests.get(f"{API}/stats", timeout=10)
    assert r.status_code == 401
    r = requests.get(f"{API}/stats", headers=ADMIN, timeout=10)
    assert r.status_code == 200
    j = r.json()
    for k in ("total_appointments", "upcoming_appointments", "total_doctors", "total_users"):
        assert k in j and isinstance(j[k], int)


# ---------------- Admin creates doctor ----------------
def test_create_doctor_forbidden_for_patient():
    r = requests.post(f"{API}/doctors", headers=PAT,
                     json={"name": "TEST_DrX", "specialty": "General", "availability": "Mon"}, timeout=10)
    assert r.status_code == 403


def test_create_doctor_admin_ok(created_ids):
    r = requests.post(f"{API}/doctors", headers=ADMIN,
                     json={"name": "TEST_Dr_Playwright", "specialty": "Testing", "availability": "Anytime"}, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == "TEST_Dr_Playwright"
    assert j["doctor_id"].startswith("doc_")
    created_ids["doctors"].append(j["doctor_id"])


# ---------------- Cleanup ----------------
def test_zzz_cleanup(created_ids):
    from pymongo import MongoClient
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "yuktik_ai")]
    if created_ids["appts"]:
        db.appointments.delete_many({"appointment_id": {"$in": created_ids["appts"]}})
    if created_ids["doctors"]:
        db.doctors.delete_many({"doctor_id": {"$in": created_ids["doctors"]}})
    db.user_sessions.delete_many({"session_token": "sess_test_logout_temp"})
    client.close()
