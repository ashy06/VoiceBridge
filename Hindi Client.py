import requests
import pyaudio
import wave
import socketio
import threading
import time
from gtts import gTTS
import io
import pygame

def play_text(text, lang='hi'):
    # Generate TTS output as a byte stream
    tts = gTTS(text=text, lang=lang)
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)

    # Initialize pygame mixer to play the audio
    pygame.mixer.init()
    pygame.mixer.music.load(audio_fp, "mp3")
    pygame.mixer.music.play()

    # Keep the program running while the audio plays
    while pygame.mixer.music.get_busy():
        continue

# Socket.IO client setup
sio = socketio.Client(logger=True, engineio_logger=True, reconnection=True, reconnection_attempts=5, reconnection_delay=2)

# Server URL (replace with your ngrok public URL)
server_url_flask = 'https://4460-34-124-197-82.ngrok-free.app/transcribe'  # Use your actual ngrok URL here

client_role = None  # Variable to track client role (client1 or client2)
waiting_for_message = threading.Event()  # Event to track when we're waiting for a server message

# Function to record audio
def record_audio(filename, duration=5, sample_rate=16000):
    chunk = 1024  # Record in chunks of 1024 samples
    format = pyaudio.paInt16  # 16 bits per sample
    channels = 1  # Mono

    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    stream = p.open(format=format,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=chunk)

    print("Recording...")

    frames = []
    for _ in range(0, int(sample_rate / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    print("Finished recording")

    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save the recorded audio as a WAV file
    wf = wave.open(filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(format))
    wf.setframerate(sample_rate)
    wf.writeframes(b''.join(frames))
    wf.close()

# Send the audio to the Flask server for transcription with language code
def send_audio_to_server(filename, language_code):
    with open(filename, 'rb') as audio_file:
        files = {'file': audio_file}
        data = {'language': language_code}
        response = requests.post(server_url_flask, files=files, data=data)

    try:
        return response.json()  # Return the server response
    except requests.exceptions.JSONDecodeError:
        return {"error": "Unable to process the response"}

# Listen for transcription and translation from the server
@sio.event
def receive_translation(data):
    print(f"\n[Server] Transcription: {data['transcription']}")
    print(f"[Server] Translation: {data['translation']}\n")
    play_text(data['translation'])
    waiting_for_message.set()  # Unblock after receiving the message

# Function to prompt the user for speaking or listening
def speak_or_listen():
    global client_role, waiting_for_message
    while True:
        try:
            choice = input("Press 'v' to speak, 'l' to listen (or 'q' to quit): ").lower()

            if choice == 'v':
                filename = 'output.wav'
                record_audio(filename, duration=5)

                # Send the recorded audio to the server
                print("Sending audio to server...")
                response = send_audio_to_server(filename, 'hi')

                if 'error' not in response:
                    print(f"[Server] Transcription: {response['transcription']}")
                    print(f"[Server] Translation: {response['translation']}")
                else:
                    print(response['error'])

            elif choice == 'l':
                
                print("Listening for incoming messages...")
                waiting_for_message.clear()  # Clear the event to wait for the message

                # Block until we receive a message from the server
                waiting_for_message.wait()

            elif choice == 'q':
                print("Quitting...")
                sio.disconnect()
                break

            else:
                print("Invalid input. Please press 'v' to speak, 'l' to listen, or 'q' to quit.")

        except ValueError:
            print("Connection lost or input stream closed. Attempting to reconnect...")
            sio.connect('https://4460-34-124-197-82.ngrok-free.app')  # Reconnect after failure

# Event to receive the assigned client role from the server
@sio.event
def client_role(data):
    global client_role
    client_role = data['role']
    print(f"Assigned client role: {client_role}")

# Main function to start the client
if __name__ == '__main__':
    try:
        # Connect to the Socket.IO server using WebSocket transport
        sio.connect('https://4460-34-124-197-82.ngrok-free.app', transports=['websocket'])

        # Wait for the role assignment before starting the loop
        while client_role is None:
            time.sleep(0.1)  # Wait until the client role is assigned

        # Start the speak or listen loop
        speak_or_listen()

    except Exception as e:
        print(f"Failed to connect or an error occurred: {e}")
