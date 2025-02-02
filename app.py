from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import asyncio
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import os
import uvicorn

# Initialize FastAPI app
app = FastAPI()

# Set up Deepgram API key (secure this with environment variables)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "d60c00514729244e27d97f343003520cdb9404ef")
URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

# Basic root route to avoid 404 errors
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Deepgram Transcription API"}

# Define a model for the incoming request data
class TranscriptionRequest(BaseModel):
    model: str = "nova-2"  # Default model

@app.post("/transcribe")
async def start_transcription(request: TranscriptionRequest):
    try:
        # Initialize the Deepgram client with the API key
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        dg_connection = deepgram.listen.live.v("1")  # Correct WebSocket method

        async def on_message(result, **kwargs):  # Removed 'self'
            sentence = result.channel.alternatives[0].transcript
            if sentence:
                print(f"Speaker: {sentence}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Options for transcription based on the model provided in the request
        options = LiveOptions(model=request.model)

        # Remove await since start() returns a boolean (synchronous)
        if not dg_connection.start(options):
            return {"error": "Failed to start connection"}

        async def send_audio():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", URL) as response:
                    async for chunk in response.aiter_bytes():
                        dg_connection.send(chunk)  # Remove await here as well

        # Start streaming the audio asynchronously
        await send_audio()

        # Finish transcription (synchronous call)
        dg_connection.finish()

        return {"message": "Transcription finished successfully"}

    except Exception as e:
        return {"error": f"Could not open socket: {str(e)}"}

# Start FastAPI app with Uvicorn, binding to the port defined by Render
if __name__ == "__main__":
    port = os.getenv("PORT", 8000)  # Get the port from environment variables
    uvicorn.run(app, host="0.0.0.0", port=int(port))
