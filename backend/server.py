"""yuktikAI FastAPI + Socket.IO server."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import socketio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yuktik")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(MONGO_URL)
    app.state.mongo = client
    app.state.db = client[DB_NAME]

    # Ensure indexes
    await app.state.db.users.create_index("email", unique=True)
    await app.state.db.users.create_index("user_id", unique=True)
    await app.state.db.user_sessions.create_index("session_token", unique=True)
    await app.state.db.doctors.create_index("doctor_id", unique=True)
    await app.state.db.appointments.create_index("appointment_id", unique=True)
    await app.state.db.appointments.create_index("starts_at")
    await app.state.db.appointments.create_index("patient_user_id")
    await app.state.db.appointments.create_index("doctor_id")
    await app.state.db.voice_sessions.create_index("session_id", unique=True)

    # Seed doctors
    from seed import seed_doctors
    added = await seed_doctors(app.state.db)
    logger.info(f"Doctors ready (seeded {added})")

    yield
    client.close()


fastapi_app = FastAPI(title="yuktikAI", lifespan=lifespan)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@fastapi_app.get("/api/health")
async def health():
    return {"status": "ok", "service": "yuktikAI"}


# Register routers
from auth import router as auth_router  # noqa: E402
from appointments import router as appts_router  # noqa: E402
from voice import router as voice_router  # noqa: E402

fastapi_app.include_router(auth_router)
fastapi_app.include_router(appts_router)
fastapi_app.include_router(voice_router)


# Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
)


@sio.event
async def connect(sid, environ):
    logger.info(f"socket connected: {sid}")


@sio.event
async def disconnect(sid):
    logger.info(f"socket disconnected: {sid}")


# Combine into a single ASGI app; socket.io mounted at /socket.io
app = socketio.ASGIApp(sio, fastapi_app, socketio_path="socket.io")
