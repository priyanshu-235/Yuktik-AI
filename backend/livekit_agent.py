import asyncio
import os
import logging
import struct
import wave
from typing import Optional
from livekit import rtc
from livekit.api import AccessToken, VideoGrants
from models import Turn
from auth import optional_user
from fastapi import Request
import io

logger = logging.getLogger("livekit_agent")

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 48000, channels: int = 1) -> bytes:
    """Convert raw PCM data to WAV format."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer.read()


class VoiceAgent:
    """Real-time voice agent using LiveKit for bidirectional audio streaming."""
    
    def __init__(self, session_id: str, db, user=None):
        self.session_id = session_id
        self.db = db
        self.user = user
        self.room: Optional[rtc.Room] = None
        self.audio_source: Optional[rtc.AudioSource] = None
        self.audio_track: Optional[rtc.LocalAudioTrack] = None
        self.is_processing = False
        self.audio_buffer = bytearray()
        self.buffer_duration = 0  # Track buffer duration in seconds
        self.silence_threshold = 0.02  # 20ms of silence before processing
        self.last_audio_time = 0
        
    async def connect(self, room_name: str):
        """Connect to LiveKit room as an agent."""
        # Create token for agent
        token = self._create_agent_token(room_name)
        
        # Connect to room
        self.room = rtc.Room()
        await self.room.connect(LIVEKIT_URL, token)
        logger.info(f"Agent connected to room: {room_name}")
        
        # Subscribe to remote tracks (user's audio)
        self.room.on("track_subscribed", self._on_track_subscribed)
        
        # Create audio source and track for TTS output (48kHz for LiveKit compatibility)
        self.audio_source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        self.audio_track = rtc.LocalAudioTrack.create_audio_track("agent-audio", self.audio_source)
        await self.room.local_participant.publish_track(self.audio_track)
        
    def _create_agent_token(self, room_name: str) -> str:
        """Create access token for agent participant."""
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(f"agent-{self.session_id}")
        token.with_name("Asha Agent")
        
        grants = VideoGrants(
            room=room_name,
            room_join=True,
            can_publish=True,
            can_subscribe=True,
        )
        token.with_grants(grants)
        
        return token.to_jwt()
    
    def _on_track_subscribed(self, track: rtc.RemoteTrack, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        """Handle when user's audio track is subscribed."""
        logger.info(f"Track subscribed: kind={track.kind} (type: {type(track.kind)}), participant={participant.identity}")
        # Check if track is audio - LiveKit uses enum value 1 for audio
        try:
            kind_value = int(track.kind)
            if kind_value == 1:
                logger.info("User audio track subscribed - starting audio stream processing")
                asyncio.create_task(self._process_audio_stream(track))
        except (ValueError, TypeError):
            logger.info(f"Could not convert track.kind to int, trying string comparison")
            if str(track.kind).lower() == 'audio':
                logger.info("User audio track subscribed - starting audio stream processing")
                asyncio.create_task(self._process_audio_stream(track))
    
    async def _process_audio_stream(self, track: rtc.RemoteTrack):
        """Process incoming audio stream in real-time."""
        audio_stream = rtc.AudioStream(track)
        frame_count = 0
        
        logger.info("Starting audio stream processing")
        
        async for frame_event in audio_stream:
            frame_count += 1
            
            if self.is_processing:
                continue  # Skip audio while processing
            
            # Get the actual audio frame from the event
            frame = frame_event.frame
            
            # Add frame data to buffer
            self.audio_buffer.extend(frame.data)
            
            # Calculate duration based on samples (assuming 48kHz)
            samples_per_frame = len(frame.data) // 2  # 16-bit audio = 2 bytes per sample
            frame_duration = samples_per_frame / 48000
            self.buffer_duration += frame_duration
            
            # Log every 100 frames
            if frame_count % 100 == 0:
                logger.info(f"Received {frame_count} frames, buffer duration: {self.buffer_duration:.2f}s")
            
            # Check if we have enough audio or silence
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_audio_time
            
            # Process if buffer has 2+ seconds or 500ms of silence
            if self.buffer_duration >= 2.0 or (self.buffer_duration >= 0.5 and time_since_last >= 0.5):
                if self.buffer_duration > 0:
                    logger.info(f"Triggering processing: buffer={self.buffer_duration:.2f}s, silence={time_since_last:.2f}s")
                    await self._process_audio_chunk()
                self.last_audio_time = current_time
    
    async def _process_audio_chunk(self):
        """Process buffered audio through STT → LLM → TTS pipeline."""
        from voice import (
            sarvam_stt,
            call_llm,
            sarvam_tts,
            _system_prompt,
            _doctors_snippet,
            _maybe_book,
            BOOK_BLOCK_RE,
            _language_for_tts,
        )
        self.is_processing = True
        
        try:
            # Convert buffer to WAV
            pcm_data = bytes(self.audio_buffer)
            
            # Clear buffer
            self.audio_buffer.clear()
            self.buffer_duration = 0
            
            # Convert PCM to WAV for Sarvam
            wav_audio = pcm_to_wav(pcm_data, sample_rate=48000, channels=1)
            
            logger.info(f"Processing audio chunk: {len(wav_audio)} bytes WAV")
            
            # STT
            transcript, lang_code = await sarvam_stt(wav_audio, "audio.wav", "audio/wav")
            if not transcript.strip():
                logger.info("No transcript from STT")
                self.is_processing = False
                return
            
            logger.info(f"Transcript: {transcript}")
            
            # Get session history
            session_doc = await self.db.voice_sessions.find_one(
                {"session_id": self.session_id}, 
                {"_id": 0}
            )
            if not session_doc:
                logger.error("Session not found")
                self.is_processing = False
                return
            
            # LLM
            doctors_snippet, doctors_lookup = await _doctors_snippet(self.db)
            sys_prompt = _system_prompt(self.user.name if self.user else None, doctors_snippet)
            
            reply = await call_llm(
                session_id=self.session_id,
                system_msg=sys_prompt,
                user_text=transcript,
                history=[Turn(**t) for t in session_doc.get("turns", [])],
            )
            
            ticket = await _maybe_book(reply, self.db, self.user, doctors_lookup)
            reply_clean = BOOK_BLOCK_RE.sub("", reply).strip()
            
            if ticket:
                reply_clean = f"{reply_clean}\n\nYour appointment id is {ticket['appointment_id'].upper()}."
            
            logger.info(f"Reply: {reply_clean}")
            
            # TTS
            tts_lang = _language_for_tts(lang_code, transcript, reply_clean)
            audio_b64 = await sarvam_tts(reply_clean, language_code=tts_lang)
            
            # Decode base64 and play
            import base64
            tts_audio = base64.b64decode(audio_b64)
            
            # Stream TTS audio to user
            await self._play_audio(tts_audio)
            
            # Persist turns
            new_turns = session_doc.get("turns", []) + [
                Turn(role="user", text=transcript).model_dump(),
                Turn(role="assistant", text=reply_clean).model_dump(),
            ]
            update = {"turns": new_turns, "language": lang_code}
            if ticket:
                update["ticket_appointment_id"] = ticket["appointment_id"]
            await self.db.voice_sessions.update_one(
                {"session_id": self.session_id}, 
                {"$set": update}
            )
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
        finally:
            self.is_processing = False
    
    async def _play_audio(self, audio_bytes: bytes):
        """Play audio through LiveKit."""
        if not self.audio_source:
            logger.error("Audio source not available")
            return
        
        logger.info(f"Playing audio: {len(audio_bytes)} bytes")
        
        try:
            # Convert 24kHz TTS audio to 48kHz for LiveKit
            # Sarvam TTS returns 24kHz, LiveKit expects 48kHz
            import numpy as np
            
            # Resample from 24kHz to 48kHz
            original_samples = len(audio_bytes) // 2  # 16-bit = 2 bytes per sample
            resampled_samples = int(original_samples * 48000 / 24000)
            
            # Convert bytes to int16 array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Simple linear interpolation for resampling
            resampled_array = np.interp(
                np.linspace(0, original_samples - 1, resampled_samples),
                np.arange(original_samples),
                audio_array
            ).astype(np.int16)
            
            # Convert back to bytes
            resampled_bytes = resampled_array.tobytes()
            
            # Stream audio in chunks to avoid large frames
            chunk_size = 9600  # 100ms at 48kHz (9600 samples * 2 bytes)
            for i in range(0, len(resampled_bytes), chunk_size):
                chunk = resampled_bytes[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    # Pad last chunk
                    chunk = chunk + b'\x00' * (chunk_size - len(chunk))
                
                frame = rtc.AudioFrame(
                    data=chunk,
                    sample_rate=48000,
                    num_channels=1,
                    samples_per_channel=len(chunk) // 2,
                )
                
                await self.audio_source.capture_frame(frame)
                # Small delay between chunks for smoother playback
                await asyncio.sleep(0.01)
            
            logger.info("Audio playback complete")
        except Exception as e:
            logger.error(f"Error in audio playback: {e}")
            import traceback
            traceback.print_exc()
    
    async def disconnect(self):
        """Disconnect from room."""
        if self.room:
            await self.room.disconnect()
            logger.info("Agent disconnected")


# Global agent registry to manage active sessions
active_agents = {}


async def get_or_create_agent(session_id: str, db, user=None) -> VoiceAgent:
    """Get existing agent or create new one."""
    if session_id in active_agents:
        return active_agents[session_id]
    
    agent = VoiceAgent(session_id, db, user)
    active_agents[session_id] = agent
    return agent


async def cleanup_agent(session_id: str):
    """Clean up agent session."""
    if session_id in active_agents:
        await active_agents[session_id].disconnect()
        del active_agents[session_id]
