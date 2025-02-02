# app.py
import os
from flask import Flask, request, jsonify
import httpx
import logging
import threading
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions

app = Flask(__name__)

# Deepgram API key and default audio URL
DEEPGRAM_API_KEY = "d60c00514729244e27d97f343003520cdb9404ef"
DEFAULT_AUDIO_URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

def stream_audio(dg_connection, audio_url, exit_event):
    try:
        with httpx.stream("GET", audio_url) as response:
            for chunk in response.iter_bytes():
                if exit_event.is_set():
                    break
                dg_connection.send(chunk)
    finally:
        dg_connection.finish()

@app.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Expects a JSON payload with an optional key "audio_url". If not provided,
    it defaults to DEFAULT_AUDIO_URL.
    """
    data = request.get_json() or {}
    audio_url = data.get("audio_url", DEFAULT_AUDIO_URL)
    
    # Initialize Deepgram client
    try:
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
    except Exception as e:
        return jsonify({"error": f"Deepgram client error: {e}"}), 500

    try:
        dg_connection = deepgram.listen.websocket.v("1")
    except Exception as e:
        return jsonify({"error": f"Could not get websocket client: {e}"}), 500

    result_holder = {"transcript": ""}
    
    def on_message(self, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            result_holder["transcript"] += transcript + " "

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

    options = LiveOptions(model="nova-2")
    
    if not dg_connection.start(options):
        return jsonify({"error": "Failed to start Deepgram connection"}), 500

    exit_event = threading.Event()
    audio_thread = threading.Thread(target=stream_audio, args=(dg_connection, audio_url, exit_event))
    audio_thread.start()
    
    # In production, consider a more dynamic method for waiting/transcription completion.
    audio_thread.join(timeout=20)
    exit_event.set()

    return jsonify(result_holder)

# In production, Render will set the PORT environment variable.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Turn off debug mode in production
    app.run(debug=False, host="0.0.0.0", port=port)
