import httpx
import threading
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

# URL for the realtime streaming audio you would like to transcribe
URL = "http://stream.live.vc.bbcmedia.co.uk/bbc_world_service"

# Your Deepgram API key
DEEPGRAM_API_KEY = 'd60c00514729244e27d97f343003520cdb9404ef'

def main():
    try:
        # Create a Deepgram client using your API key
        deepgram: DeepgramClient = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        
        # Create a synchronous websocket connection to Deepgram
        dg_connection = deepgram.listen.websocket.v("1")

        # Define a callback to handle incoming transcript messages
        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            print(f"speaker: {sentence}")

        # Register the transcript handler
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        # Prepare connection options (using model "nova-2" as per docs)
        options = LiveOptions(model="nova-2")

        # Start the connection (synchronously)
        if dg_connection.start(options) is False:
            print("Failed to start connection")
            return

        lock_exit = threading.Lock()
        exit_flag = False  # using a local flag to indicate when to exit

        # Define a worker thread that streams audio data using httpx
        def myThread():
            nonlocal exit_flag
            with httpx.stream("GET", URL) as r:
                for data in r.iter_bytes():
                    lock_exit.acquire()
                    if exit_flag:
                        lock_exit.release()
                        break
                    lock_exit.release()
                    dg_connection.send(data)

        # Start the worker thread to fetch audio and send it to Deepgram
        myHttp = threading.Thread(target=myThread)
        myHttp.start()

        # Wait for user input to stop recording
        input("\n\nPress Enter to stop recording...\n\n")
        lock_exit.acquire()
        exit_flag = True
        lock_exit.release()

        # Wait for the HTTP thread to finish
        myHttp.join()

        # Close the Deepgram connection gracefully
        dg_connection.finish()

        print("Finished")

    except Exception as e:
        print(f"Could not open socket: {e}")
        return

if __name__ == "__main__":
    main()
