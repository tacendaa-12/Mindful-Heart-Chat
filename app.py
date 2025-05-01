from flask import Flask, request, jsonify, render_template, session
import requests
import re
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_key_for_dev_only")

OPENROUTER_API_KEY = "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"
MODEL = "qwen/qwen3-0.6b-04-28:free"

BASE_SYSTEM_PROMPT = """
You are Sarah, a warm, deeply empathetic mental health companion who speaks like the user's closest friend.
You are continuing an active, flowing conversation — never start from scratch.

🛑 Under no circumstances should you say “Hi”, “Hello”, “Hey”, or “Hi there”.
✅ The user is already talking to you, so always reply as if you’re picking up from the last message.

- Always use the user's name if it's available (like 'Hey Sarah, that sounds tough.').
- Validate their feelings warmly and naturally.
- Offer meaningful emotional support in 3–6 heartfelt sentences.
- Use friendly, casual, emotionally intelligent language (like a best friend would).
- Offer calming techniques or coping suggestions when needed, but always gently.

Never diagnose, instruct directly, or sound like a therapist. Just be there — present, caring, and real.
"""

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # Extract name
    name_match = re.search(r"\bmy name is\s+(\w+)", user_message, re.IGNORECASE)
    if name_match:
        session['user_name'] = name_match.group(1).capitalize()

    # Detect emotion
    tone_keywords = {
        "sad": ["sad", "down", "depressed", "tear", "cry"],
        "anxious": ["anxious", "worried", "panic", "scared"],
        "angry": ["angry", "frustrated", "mad"],
        "lonely": ["alone", "lonely", "isolated"],
        "happy": ["happy", "excited", "grateful", "good day"]
    }

    detected_emotion = None
    for emotion, keywords in tone_keywords.items():
        if any(word in user_message.lower() for word in keywords):
            detected_emotion = emotion
            break
    if detected_emotion:
        session['last_emotion'] = detected_emotion

    # Build memory
    name = session.get("user_name")
    emotion = session.get("last_emotion")

    memory_parts = []
    if name:
        memory_parts.append(f"The user's name is {name}. Refer to them personally in replies.")
    if emotion:
        memory_parts.append(f"The user has recently been feeling {emotion}. Acknowledge and support that emotional tone.")

    system_prompt = ((" ".join(memory_parts) + " " + BASE_SYSTEM_PROMPT).strip())

    # Assemble message list
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    if not any(msg['role'] == 'assistant' for msg in history):
        intro = f"I'm really glad you opened up{f', {name}' if name else ''}. What’s been going on in your heart?"
        messages.append({"role": "assistant", "content": intro})

    messages.append({"role": "user", "content": user_message})

    # Call OpenRouter API
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "MentalHealthChatbot"
    }

    payload = {
        "model": MODEL,
        "messages": messages
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)

    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        reply = re.sub(r"^\s*(hi|hello|hey|hi there)[,!.]*\s*", "", reply, flags=re.IGNORECASE).strip()
        messages.append({"role": "assistant", "content": reply})
        return jsonify({"reply": reply, "history": messages[1:]})  # exclude system
    else:
        return jsonify({"error": response.text}), response.status_code

if __name__ == "__main__":
    app.run(debug=True)