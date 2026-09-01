# yuktikAI

Voice receptionist for a demo multispeciality clinic. Patients talk to **Asha** in English or Hindi: clinic FAQs, light symptom triage, and appointment booking. Bookings produce a web ticket and a PDF.

Turn-based voice (tap to record, tap to send) — not a live phone call.

## Features

- Google sign-in (Identity Services); first user is **admin**
- Roles: **patient**, **doctor**, **admin**
- Voice agent: Sarvam speech-to-text → Gemini → Sarvam text-to-speech
- Structured booking from the model reply (validated against doctors in MongoDB)
- Appointment list, doctor/admin dashboards, PDF ticket
- Hindi / English replies (language follows the caller)

## Architecture

```
Browser (React)
  │  HTTPS + session cookie
  │  POST /api/voice/turn  (WAV)
  ▼
Uvicorn  ── FastAPI (REST)
         └── Socket.IO (appointment live updates)
                │
                ├─ MongoDB Atlas
                ├─ Google (ID token verify, Gemini)
                └─ Sarvam (STT + TTS)
```

**One spoken turn**

1. Browser records audio, converts **WebM → WAV** (Sarvam STT does not accept WebM/Opus).
2. `POST /api/voice/turn` runs STT → LLM (last 6 turns + clinic prompt) → optional book → TTS.
3. UI plays the reply. After a successful booking, speech finishes first; then a **Show ticket** button appears (navigation used to cut off audio).

REST and Socket.IO share one ASGI app: `uvicorn server:app`.

## Tech stack

| | |
|---|---|
| Frontend | React 18, CRA + CRACO, Tailwind, Axios, Socket.IO client |
| Backend | FastAPI, Uvicorn, Motor (async MongoDB), Pydantic |
| Auth | Google OAuth ID tokens, opaque HttpOnly session cookie |
| Speech | Sarvam Saaras (STT), Bulbul (TTS) |
| LLM | Google Gemini (`GEMINI_MODEL`) |
| PDF | ReportLab |

## Repository layout

```
backend/          FastAPI app (server.py, auth, voice, appointments)
frontend/         React UI
docs/             Extra notes (interview / design)
```

## Prerequisites

- Python 3.11+ (3.13 works)
- Node.js 18+
- MongoDB (Atlas or local)
- [Google Cloud OAuth client](https://console.cloud.google.com/) (GIS)
- [Google AI Studio](https://aistudio.google.com/) API key
- [Sarvam](https://www.sarvam.ai/) API key

## Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Unix:    source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=YUKTIKAI
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-2.5-flash
SARVAM_API_KEY=your-sarvam-key
```

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

Doctors are seeded on startup if the collection is empty.

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

Authorized JavaScript origin and redirect URI in Google Cloud must include your frontend origin (e.g. `http://localhost:3000`).

```bash
npm start
```

## Auth

1. Frontend loads GIS and the client ID from `GET /api/auth/config`.
2. Google returns an ID token; `POST /api/auth/google` verifies it (`google-auth`).
3. Server upserts the user and sets `session_token` (HttpOnly cookie, 7 days). Axios uses `withCredentials: true`.

Cookie flags are `Secure` + `SameSite=None` for split origin (UI vs API). On plain `http://localhost` some browsers will not store that cookie — use HTTPS or relax flags in development if login appears to fail.

## Voice API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/voice/session` | Create a conversation |
| `POST` | `/api/voice/turn` | Audio in → transcript, reply, WAV, optional ticket |
| `POST` | `/api/voice/turn/text` | Same without audio (testing) |

The model may emit a `<<<BOOK … BOOK>>>` JSON block. The server parses it, checks `doctor_id` and a future IST time, then inserts an appointment.

Gemini **free-tier** Flash quotas are small (on the order of tens of requests per day). HTTP 429 is expected if you exceed them. Google may report the quota under a related model name (e.g. `gemini-3-flash`) even when `GEMINI_MODEL` is `gemini-2.5-flash`.

## Roles and routes

| Path | Who |
|---|---|
| `/talk` | Signed-in users (voice) |
| `/appointments` | Patients |
| `/ticket/:id` | Signed-in users |
| `/doctor` | `doctor`, `admin` |
| `/admin`, `/admin/users` | `admin` |

## Configuration notes

- Do not put Gemini or Sarvam keys in `REACT_APP_*` variables.
- `load_dotenv(override=True)` so `backend/.env` wins over leftover shell env vars.

## License

ISC (frontend package). Add a repo-level license if you publish this as open source.
