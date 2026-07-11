import os
import logging
import httpx
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    RunContext,
    stt,
    tts,
    llm,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("livekit_agent_v2")
logger.setLevel(logging.INFO)

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class SarvamSTT(stt.STT):
    """Custom STT using Sarvam API."""
    
    def __init__(self, language='hi-IN', model='saarika:v2.5'):
        super().__init__()
        self.language = language
        self.model = model
    
    async def recognize(self, frame: stt.AudioFrame) -> stt.SpeechEvent:
        """Recognize speech from audio frame."""
        # Convert frame to bytes
        audio_data = frame.data.tobytes()
        
        # Call Sarvam STT API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers={"api-subscription-key": SARVAM_API_KEY},
                files={"file": ("audio.wav", audio_data, "audio/wav")},
                data={"language_code": self.language, "model": self.model}
            )
            response.raise_for_status()
            result = response.json()
        
        transcript = result.get("transcript", "")
        if transcript:
            return stt.SpeechEvent(
                alternatives=[stt.SpeechAlternative(text=transcript)]
            )
        return None


class SarvamTTS(tts.TTS):
    """Custom TTS using Sarvam API."""
    
    def __init__(self, target_language_code='hi-IN', speaker='anushka'):
        super().__init__()
        self.target_language_code = target_language_code
        self.speaker = speaker
    
    async def synthesize(self, text: str) -> tts.SynthesizedAudio:
        """Synthesize speech from text."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SARVAM_TTS_URL,
                headers={"api-subscription-key": SARVAM_API_KEY},
                json={
                    "inputs": [text],
                    "target_language_code": self.target_language_code,
                    "speaker": self.speaker,
                    "pitch": 0,
                    "pace": 1.0,
                    "loudness": 1.5,
                    "samplerate": 24000,
                }
            )
            response.raise_for_status()
            result = response.json()
        
        audio_data = result.get("audio", "")
        if audio_data:
            import base64
            audio_bytes = base64.b64decode(audio_data)
            return tts.SynthesizedAudio(data=audio_bytes, sample_rate=24000)
        return None


class GeminiLLM(llm.LLM):
    """Custom LLM using Google Gemini API."""
    
    def __init__(self, model="gemini-3-flash-preview"):
        super().__init__()
        self.model = model
        self.api_key = GEMINI_API_KEY
    
    async def chat(self, chat_ctx: llm.ChatContext) -> llm.ChatCompletion:
        """Generate chat completion using Gemini."""
        from google import genai
        from google.genai import types as genai_types
        
        client = genai.Client(api_key=self.api_key)
        
        # Convert LiveKit chat context to Gemini format
        contents = []
        for msg in chat_ctx.messages:
            if msg.role == "system":
                # Gemini doesn't have system messages, prepend to first user message
                continue
            elif msg.role == "user":
                role = "user"
            elif msg.role == "assistant":
                role = "model"
            else:
                continue
            
            contents.append(genai_types.Content(
                role=role,
                parts=[genai_types.Part.from_text(text=msg.content)]
            ))
        
        # Add system instruction if present
        system_instruction = None
        for msg in chat_ctx.messages:
            if msg.role == "system":
                system_instruction = msg.content
                break
        
        cfg = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.4
        )
        
        async def _sync_call():
            return client.models.generate_content(
                model=self.model,
                contents=contents,
                config=cfg
            )
        
        import asyncio
        resp = await asyncio.to_thread(_sync_call)
        
        # Convert Gemini response to LiveKit format
        response_text = getattr(resp, "text", "") or ""
        
        return llm.ChatCompletion(
            id=str(id(resp)),
            choices=[
                llm.Choice(
                    message=llm.Message(
                        role="assistant",
                        content=response_text
                    )
                )
            ]
        )


class VoiceAgent(Agent):
    """Real-time voice agent using LiveKit Agents framework with custom Sarvam STT/TTS and Gemini LLM."""
    
    def __init__(self):
        super().__init__(
            instructions="You are Asha, a friendly voice assistant for Digitix Multispeciality Clinic. Greet the user warmly and help them with their questions. Be conversational and natural.",
            stt=SarvamSTT(language='hi-IN', model='saarika:v2.5'),
            llm=GeminiLLM(model="gemini-3-flash-preview"),
            tts=SarvamTTS(target_language_code='hi-IN', speaker='anushka'),
        )
    
    async def on_enter(self) -> None:
        """Called when the agent starts."""
        logger.info("Agent started")
        # Generate initial greeting
        await self.session.generate_reply()


async def entrypoint(ctx: JobContext):
    """Entry point for the LiveKit agent worker."""
    logger.info(f"Agent worker started for room: {ctx.room.name}")
    
    # Create the agent
    agent = VoiceAgent()
    
    # Create and start the session
    session = AgentSession()
    
    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
