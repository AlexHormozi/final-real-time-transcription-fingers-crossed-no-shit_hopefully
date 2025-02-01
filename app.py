# app.py

import os
import httpx
import threading
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

# Retrieve your Deepgram API key from environment variables
DEEPGRAM_API_KEY = os.getenv('d60c00514729244e27d97f343003520cdb9404ef')

# URL for the realtime streaming audio you would like to transcribe
URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

def main():
    try:
        # Initialize the Deepgram client with the API key
        deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)

        # Create a websocket connection to Deepgram
        dg_connection = deepgram.listen.websocket.v("1")

        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            print(f"speaker: {sentence}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Connect to websocket
        options = LiveOptions(model="nova-2")

        print("\n\nPress Enter to stop recording...\n\n")
        if not dg_connection.start(options):
            print("Failed to start connection")
            return

        lock_exit = threading.Lock()
        exit = False

        # Define a worker thread
        def myThread():
            with httpx.stream("GET", URL) as r:
                for data in r.iter_bytes():
                    lock_exit.acquire()
                    if exit:
                        break
                    lock_exit.release()

                    dg_connection.send(data)

        # Start the worker thread
        myHttp = threading.Thread(target=myThread)
        myHttp.start()

        # Signal finished
        input("")
        lock_exit.acquire()
        exit = True
        lock_exit.release()

        # Wait for the HTTP thread to close and join
        myHttp.join()

        # Indicate that we've finished
        dg_connection.finish()

        print("Finished")

    except Exception as e:
        print(f"Could not open socket: {e}")
        return

if __name__ == "__main__":
    main()
