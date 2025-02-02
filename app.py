from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import asyncio
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import os
import uvicorn

app = FastAPI()

# Set up Deepgram API key (secure this with environment variables)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "d60c00514729244e27d97f343003520cdb9404ef")
URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Deepgram Transcription API"}

class TranscriptionRequest(BaseModel):
    model: str = "nova-2"  # Default model

@app.post("/transcribe")
async def start_transcription(request: TranscriptionRequest):
    try:
        # Initialize the Deepgram client with the API key
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        # Use the non-deprecated WebSocket method
        dg_connection = deepgram.listen.websocket.v("1")
        
        # Define the callback using a flexible signature
        async def on_message(*args, **kwargs):
            # For debugging: print what is passed to the callback
            print("on_message called with args:", args, "kwargs:", kwargs)
            # Attempt to get the result from positional arguments or kwargs
            result = args[0] if args else kwargs.get("result", None)
            if result:
                sentence = result.channel.alternatives[0].transcript
                if sentence:
                    print(f"Speaker: {sentence}")
        
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Options for transcription based on the model provided in the request
        options = LiveOptions(model=request.model)

        # Remove 'await' because start() returns a bool (synchronously)
        if not dg_connection.start(options):
            return {"error": "Failed to start connection"}

        async def send_audio():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", URL) as response:
                    async for chunk in response.aiter_bytes():
                        dg_connection.send(chunk)

        # Start streaming the audio asynchronously
        await send_audio()

        # Finish transcription (synchronous call)
        dg_connection.finish()

        return {"message": "Transcription finished successfully"}

    except Exception as e:
        return {"error": f"Could not open socket: {str(e)}"}

if __name__ == "__main__":
    port = os.getenv("PORT", 8000)  # Get the port from environment variables
    uvicorn.run(app, host="0.0.0.0", port=int(port))
