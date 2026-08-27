import os
import re
import asyncio
import tempfile
from datetime import datetime
import requests
import wikipedia
from flask import Flask, render_template, request, jsonify, send_file
from google import genai
import edge_tts

app = Flask(__name__, template_folder='.')

# ==============================================================================
# ⚠️ PASTE YOUR GEMINI API KEY BELOW ⚠️
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6I49ySakhfSrBUQXhGVCVZlDFDw0gxF0-dkOie1T6tBqQ")

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception:
    client = None
    print("WARNING: Gemini API Key is missing or invalid.")

JARVIS_INSTRUCTION = (
    "You are J.A.R.V.I.S., an intelligent, witty, and loyal AI assistant. "
    "Keep answers crisp, tactical, sophisticated, and slightly sarcastic when appropriate. "
    "Address the user as 'Captain'."
)

def process_zero_token_commands(user_msg):
    """Handles local queries for free without using the Gemini API."""
    msg_lower = user_msg.lower().strip()

    # 1. Creator / Identity (From your exact requested lore)
    if re.search(r"who (made|created|built) you|who is your creator", msg_lower):
        return "I am created by Tony Stark also known as Iron Man. After my death by Ultron, I am recreated by firegamerhero from scratch in small scale."

    # 2. Time
    if re.search(r"what time is it|current time|time", msg_lower) and len(msg_lower) < 25:
        now = datetime.now().strftime("%I:%M %p")
        return f"The current system time is {now}, Captain."

    # 3. Weather via Open-Meteo (Free, No Auth)
    city_match = re.search(r"weather in ([\w\s]+)", msg_lower)
    if city_match:
        city = city_match.group(1).strip()
        try:
            # Geocode the city to get Latitude and Longitude
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
            geo_res = requests.get(geo_url).json()
            if geo_res.get("results"):
                lat = geo_res["results"][0]["latitude"]
                lon = geo_res["results"][0]["longitude"]
                
                # Fetch Weather data
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                w_res = requests.get(weather_url).json()
                temp = w_res["current_weather"]["temperature"]
                return f"Scanning atmospheric conditions. The current temperature in {city.title()} is {temp} degrees Celsius."
        except Exception:
            pass # If API fails, fall through to Gemini

    # 4. Wikipedia Summaries (Free)
    if msg_lower.startswith("who is ") or msg_lower.startswith("what is "):
        query = msg_lower.replace("who is ", "").replace("what is ", "").strip()
        try:
            summary = wikipedia.summary(query, sentences=2)
            return f"According to local databanks: {summary}"
        except Exception:
            pass # If article isn't found, fall through to Gemini

    return None # Return None if no local match is found (Triggering Gemini)

@app.route("/")
def home():
    # Serves the index.html file we created
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    if not user_message:
        return jsonify({"error": "Empty command."}), 400

    # Step 1: Check Zero-Token Routes first
    local_response = process_zero_token_commands(user_message)
    if local_response:
        return jsonify({"reply": local_response})

    # Step 2: Fallback to Gemini if it's a complex query
    if not client or GEMINI_API_KEY == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        return jsonify({"reply": "API Key offline. I cannot access the main neural cortex."})

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config={
                "system_instruction": JARVIS_INSTRUCTION,
                "temperature": 0.7,
            }
        )
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"reply": f"Neural uplink failed. Error: {str(e)}"})

# --- TEXT TO SPEECH (edge-tts) ---
async def generate_audio(text, output_file):
    # Using a sophisticated British voice for that JARVIS feel
    communicate = edge_tts.Communicate(text, "en-GB-RyanNeural", rate="+5%", pitch="-2Hz")
    await communicate.save(output_file)

@app.route("/tts", methods=["GET"])
def tts():
    text = request.args.get("text", "System online.")
    
    # Create a temporary MP3 file on the server
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "jarvis_tx.mp3")
    
    # Run the async edge-tts generation synchronously for Flask
    asyncio.run(generate_audio(text, file_path))
    
    # Send the generated audio file back to the browser
    return send_file(file_path, mimetype="audio/mpeg")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
