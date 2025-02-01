from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import threading
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import os
import uvicorn

# Initialize FastAPI app
app = FastAPI()

# Set up Deepgram API key (secure this with environment variables)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "d60c00514729244e27d97f343003520cdb9404ef")
URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

# Define a model for the incoming request data
class TranscriptionRequest(BaseModel):
    model: str = "nova-2"  # Default model

@app.post("/transcribe")
async def start_transcription(request: TranscriptionRequest):
    try:
        # Initialize the Deepgram client with the API key
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        dg_connection = deepgram.listen.websocket.v("1")

        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            print(f"speaker: {sentence}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Options for transcription based on the model provided in the request
        options = LiveOptions(model=request.model)

        if not dg_connection.start(options):
            return {"error": "Failed to start connection"}

        lock_exit = threading.Lock()
        exit = False

        # Worker thread to handle audio stream
        def myThread():
            with httpx.stream("GET", URL) as r:
                for data in r.iter_bytes():
                    lock_exit.acquire()
                    if exit:
                        break
                    lock_exit.release()
                    dg_connection.send(data)

        myHttp = threading.Thread(target=myThread)
        myHttp.start()

        # Signal finished
        input("Press Enter to stop recording...\n")
        lock_exit.acquire()
        exit = True
        lock_exit.release()

        myHttp.join()

        dg_connection.finish()

        return {"message": "Transcription finished successfully"}

    except Exception as e:
        return {"error": f"Could not open socket: {str(e)}"}

# Start FastAPI app with Uvicorn, binding to the port defined by Render
if __name__ == "__main__":
    port = os.getenv("PORT", 8000)  # Get the port from environment variables
    uvicorn.run(app, host="0.0.0.0", port=int(port))  # Bind to port dynamically
