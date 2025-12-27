from flask import Flask, request, jsonify
import torch
from omegaconf import OmegaConf
import urllib.request
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

app = Flask(__name__)

url = "https://raw.githubusercontent.com/snakers4/silero-models/master/models.yml"
urllib.request.urlretrieve(url, "latest_silero_models.yml")

models = OmegaConf.load("latest_silero_models.yml")

language = "en"
model_id = "v3_en"
device = torch.device("cpu")

model, _ = torch.hub.load(
    repo_or_dir="snakers4/silero-models",
    model="silero_tts",
    language=language,
    speaker=model_id,
)
model.to(device)

recognizer = sr.Recognizer()
engine = pyttsx3.init()


@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "Hello from Silero TTS")
    speaker = data.get("speaker", "en_10")
    sample_rate = 24000

    # Generate audio
    audio = model.apply_tts(
        text=text,
        speaker=speaker,
        sample_rate=sample_rate,
        put_accent=True,
        put_yo=True,
    )

    # Play audio automatically
    sd.play(audio, sample_rate)
    sd.wait()

    return jsonify({"status": "ok", "text": text, "speaker": speaker})


@app.route("/stt", methods=["GET"])
def stt():
    with sr.Microphone() as source:
        print("🎤 Speak something...")
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio)
        print("✅ You said:", text)
        return jsonify({"status": "ok", "transcription": text})
    except sr.UnknownValueError:
        return jsonify({"status": "error", "message": "Could not understand audio"})
    except sr.RequestError as e:
        return jsonify({"status": "error", "message": f"API Error: {e}"})


# 🏠 Home Route
@app.route("/")
def home():
    return jsonify({
        "message": "Speech Server is running!",
        "routes": {
            "POST /tts": "Convert text to speech",
            "GET /stt": "Convert microphone speech to text"
        }
    })


# ---------- Run Server ----------
if __name__ == "__main__":
    port = 5000
    print(f"🚀 Server running at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
