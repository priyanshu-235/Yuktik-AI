import os
from typing import Optional
from fastapi import HTTPException
from livekit.api import LiveKitAPI, CreateRoomRequest, ListRoomsRequest, AccessToken, VideoGrants

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
    raise RuntimeError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in environment")


def create_access_token(room_name: str, participant_name: str) -> str:
    """Create a LiveKit access token for a participant using v1.x API."""
    grants = VideoGrants(
        room=room_name,
        room_join=True,
        can_publish=True,
        can_subscribe=True,
    )
    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(participant_name)
    token.with_name(participant_name)
    token.with_grants(grants)
    return token.to_jwt()


async def create_room(room_name: str) -> dict:
    """Create a LiveKit room asynchronously."""
    async with LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) as api_client:
        try:
            req = CreateRoomRequest(name=room_name, empty_timeout=300, max_participants=10)
            room = await api_client.room.create_room(req)
            return {
                "sid": room.sid,
                "name": room.name,
            }
        except Exception as e:
            # Room might already exist, try to get it
            try:
                rooms_res = await api_client.room.list_rooms(ListRoomsRequest())
                rooms = rooms_res if isinstance(rooms_res, list) else getattr(rooms_res, 'rooms', [])
                for r in rooms:
                    if r.name == room_name:
                        return {"sid": r.sid, "name": r.name}
                raise HTTPException(500, f"Failed to create or find room: {e}")
            except Exception as e2:
                raise HTTPException(500, f"Failed to create room: {e2}")
