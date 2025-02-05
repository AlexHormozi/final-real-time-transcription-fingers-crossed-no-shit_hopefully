from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import time
import threading
import httpx
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

app = Flask(__name__)

# Initialize CORS to allow Bubble.io
CORS(app, origins=["https://testing-voi-ce--translati.bubbleapps.io"])

# Initialize WebSocket support
socketio = SocketIO(app, cors_allowed_origins="*")

# Deepgram API key and default audio URL
DEEPGRAM_API_KEY = "d60c00514729244e27d97f343003520cdb9404ef"
DEFAULT_AUDIO_URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

# Function to stream audio to Deepgram
def stream_audio(dg_connection, audio_url, exit_event):
    try:
        with httpx.stream("GET", audio_url) as response:
            for chunk in response.iter_bytes():
                if exit_event.is_set():
                    break
                dg_connection.send(chunk)
    finally:
        dg_connection.finish()

# WebSocket connection event
@socketio.on("connect")
def handle_connect():
    print("Client connected!")
    emit("server_response", {"message": "Connected to WebSocket!"})

# WebSocket event to handle transcription
@socketio.on("start_transcription")
def start_transcription():
    data = request.get_json() or {}
    audio_url = data.get("audio_url", DEFAULT_AUDIO_URL)

    # Initialize Deepgram client
    try:
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
    except Exception as e:
        emit("error", {"message": f"Deepgram client error: {e}"})
        return

    try:
        dg_connection = deepgram.listen.websocket.v("1")
    except Exception as e:
        emit("error", {"message": f"Could not get websocket client: {e}"})
        return

    result_holder = {"transcript": ""}

    def on_message(self, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            result_holder["transcript"] += transcript + " "
            socketio.emit("transcription_update", {"transcript": transcript})

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

    options = LiveOptions(model="nova-2")

    if not dg_connection.start(options):
        emit("error", {"message": "Failed to start Deepgram connection"})
        return

    exit_event = threading.Event()
    audio_thread = threading.Thread(target=stream_audio, args=(dg_connection, audio_url, exit_event))
    audio_thread.start()
    
    audio_thread.join(timeout=20)
    exit_event.set()

    emit("transcription_complete", {"full_transcript": result_holder["transcript"]})

# HTTP Route for stream transcription (Optional)
@app.route("/stream_transcription", methods=["GET"])
def stream_transcription():
    def generate():
        while True:
            socketio.sleep(1)
    return Response(generate(), content_type='text/event-stream')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, debug=False, host="0.0.0.0", port=port)
