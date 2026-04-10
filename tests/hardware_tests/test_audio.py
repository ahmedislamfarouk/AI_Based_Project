import pyaudio
import wave
import time

def test_audio():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 3
    WAVE_OUTPUT_FILENAME = "test_output.wav"

    p = pyaudio.PyAudio()

    print("--- Testing Audio Capture ---")
    print(f"Recording for {RECORD_SECONDS} seconds...")

    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        frames = []

        for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)

        print("Recording finished.")

        stream.stop_stream()
        stream.close()

        # Save to file
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        print(f"Audio saved to {WAVE_OUTPUT_FILENAME}")

        print("\n--- Testing Audio Playback ---")
        print("Playing back recorded audio...")
        
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'rb')
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)

        data = wf.readframes(CHUNK)
        while len(data) > 0:
            stream.write(data)
            data = wf.readframes(CHUNK)

        stream.stop_stream()
        stream.close()
        print("Playback finished.")

    except Exception as e:
        print(f"Error during audio test: {e}")
        print("\nTip: Ensure your microphone and speakers are connected.")
    
    finally:
        p.terminate()

if __name__ == "__main__":
    test_audio()
