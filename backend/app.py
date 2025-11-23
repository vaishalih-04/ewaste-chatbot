import os
import io
import json
from flask import Flask, render_template, request, jsonify
from PIL import Image
import numpy as np
from tensorflow.keras.models import load_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
DATA_DIR = os.path.join(BASE_DIR, "data")

MODEL_PATH = os.path.join(MODEL_DIR, "ewaste_model.h5")
CLASS_INDICES_PATH = os.path.join(MODEL_DIR, "class_indices.json")
DISPOSAL_RULES_PATH = os.path.join(DATA_DIR, "disposal_rules.json")

IMG_SIZE = (224, 224)
CONFIDENCE_THRESHOLD = 0.6

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(BASE_DIR), "frontend", "templates"),
    static_folder=os.path.join(os.path.dirname(BASE_DIR), "frontend", "static")
)

# Lazy loading so app can start even if model isn't trained yet
_model = None
_index_to_class = None
_disposal_rules = None


def load_assets():
    global _model, _index_to_class, _disposal_rules
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(
                f"Model file not found at {MODEL_PATH}. "
                "Train the model first by running model_training/train_model.py"
            )
        _model = load_model(MODEL_PATH)

    if _index_to_class is None:
        if not os.path.exists(CLASS_INDICES_PATH):
            raise RuntimeError(
                f"class_indices.json not found at {CLASS_INDICES_PATH}. "
                "It should be created by the training script."
            )
        with open(CLASS_INDICES_PATH, "r") as f:
            _index_to_class = json.load(f)

    if _disposal_rules is None:
        if not os.path.exists(DISPOSAL_RULES_PATH):
            raise RuntimeError(
                f"disposal_rules.json not found at {DISPOSAL_RULES_PATH}. "
                "Create it under backend/data."
            )
        with open(DISPOSAL_RULES_PATH, "r") as f:
            _disposal_rules = json.load(f)


def preprocess_image(image: Image.Image) -> np.ndarray:
    image = image.convert("RGB")
    image = image.resize(IMG_SIZE)
    arr = np.array(image) / 255.0
    arr = np.expand_dims(arr, axis=0)
    return arr


def build_maps_link(lat=None, lng=None):
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/e-waste+recycling+centre/@{lat},{lng},14z"
    return "https://www.google.com/maps/search/e-waste+recycling+centre+near+me"


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    load_assets()

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)

    try:
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))
        x = preprocess_image(image)

        preds = _model.predict(x)[0]
        best_idx = int(np.argmax(preds))
        confidence = float(preds[best_idx])

        class_name = _index_to_class.get(str(best_idx), "Unknown")
        maps_link = build_maps_link(lat, lng)

        # fallback for low confidence
        if confidence < CONFIDENCE_THRESHOLD or class_name == "Unknown":
            return jsonify({
                "product_name": "Uncertain item",
                "predicted_class": class_name,
                "confidence": confidence,
                "category": "Possibly E-waste",
                "disposal_steps": [
                    "I am not fully confident about this item.",
                    "If it is an electrical or electronic product, please avoid throwing it in normal dustbin.",
                    "Take it to an authorised e-waste collection centre for guidance."
                ],
                "hazards": "Electronic items may contain hazardous materials.",
                "tips": "Show this item to staff at a recycling centre.",
                "nearest_recycling_link": maps_link
            })

        rules = _disposal_rules.get(class_name, {})
        product_name = rules.get("display_name", class_name)
        category = rules.get("category", "E-waste")
        disposal_steps = rules.get("disposal_steps", [])
        hazards = rules.get("hazards", "")
        tips = rules.get("tips", "")

        return jsonify({
            "product_name": product_name,
            "predicted_class": class_name,
            "confidence": confidence,
            "category": category,
            "disposal_steps": disposal_steps,
            "hazards": hazards,
            "tips": tips,
            "nearest_recycling_link": maps_link
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def generate_chat_reply(user_message: str, last_class: str = None, last_name: str = None) -> str:
    """
    Smarter rule-based chatbot:
    - Handles greetings, thanks, intro questions
    - Answers general e-waste FAQs
    - Uses disposal_rules + last detected item for specific questions
    - Politely rejects irrelevant questions
    """
    msg_raw = user_message.strip()
    msg = msg_raw.lower()

    # 1) Greetings
    if any(word in msg for word in ["hello", "hi", "hi!", "hey", "good morning", "good afternoon", "good evening"]):
        if last_name:
            return f"Hello! 😊 I recently detected <b>{last_name}</b>. You can ask me how to dispose it safely or any e-waste question."
        return "Hello! 😊 I am your e-waste assistant. You can upload an image of an electronic item and ask me how to dispose it safely."

    # 2) Thanks / bye
    if any(word in msg for word in ["thank", "thanks", "thank you", "tnx", "thx", "bye", "goodbye"]):
        return "You're welcome! ♻️ If you have more questions about e-waste or another item, just ask."

    # 3) Who are you / what can you do?
    if "who are you" in msg or "what can you do" in msg or "who r u" in msg:
        return (
            "I am an e-waste assistant chatbot. I can:<br>"
            "- Identify many electronic items from an image (like battery, mobile, printer, TV, etc.)<br>"
            "- Tell you how to dispose them safely<br>"
            "- Explain why e-waste is dangerous<br>"
            "- Help you find nearby recycling centres using Google Maps."
        )

    # 4) Completely irrelevant / off-topic questions
    irrelevant_keywords = [
        "cricket", "football", "movie", "actor", "actress", "politics", "song",
        "story", "math", "science", "chemistry", "physics", "coding", "python",
        "java", "food", "recipe", "love", "relationship", "weather", "news"
    ]
    if any(word in msg for word in irrelevant_keywords):
        return (
            "Sorry, I’m just an e-waste chatbot 😅.<br>"
            "I can help you with identifying electronics and teaching you how to dispose them safely.<br><br>"
            "For other questions, you can contact my elder brother <b>ChatGPT</b> — he knows everything! 🤖✨"
        )

    # 5) General: what is e-waste?
    if "what is e-waste" in msg or ("what" in msg and "e waste" in msg):
        return (
            "E-waste (electronic waste) is any discarded electrical or electronic item, such as mobiles, laptops, TVs, "
            "batteries, chargers, printers, and so on. These items contain metals, plastics and chemicals that can "
            "pollute soil and water and can harm human health if they are dumped or burnt instead of being recycled properly."
        )

    # 6) Why is e-waste dangerous / bad / harmful?
    if ("why" in msg and "e-waste" in msg) or ("e-waste" in msg and any(w in msg for w in ["dangerous", "harmful", "bad"])):
        return (
            "E-waste is dangerous because it often contains hazardous substances like lead, mercury, cadmium and brominated "
            "flame retardants. If e-waste is thrown in normal dustbins, dumped or burnt, these substances can leak into the "
            "air, soil and water. This can cause health problems (like nerve damage and cancers) and long-term environmental damage."
        )

    # 7) Why not throw in dustbin / normal garbage?
    if any(word in msg for word in ["dustbin", "trash", "garbage", "normal bin", "normal dustbin"]):
        return (
            "Electronic items should not be thrown in the normal dustbin. They contain metals, chemicals and sometimes batteries "
            "that can leak or catch fire. Instead, always hand over e-waste to an authorised e-waste collection centre or recycler "
            "so that useful materials can be recovered safely."
        )

    # 8) What items count as e-waste / examples
    if "examples of e-waste" in msg or ("what" in msg and "e-waste items" in msg) or ("types of e-waste" in msg):
        return (
            "Common examples of e-waste include:<br>"
            "- Mobile phones, tablets, laptops, computers<br>"
            "- Keyboards, mouse, chargers, cables, earphones<br>"
            "- Televisions, printers, scanners, media players<br>"
            "- Microwaves, washing machines and other appliances with electronics<br>"
            "- Batteries and circuit boards (PCBs)<br>"
            "All of these should be sent to e-waste recyclers instead of normal dustbins."
        )

    # 9) How to find recycling centres?
    if "recycling centre" in msg or "recycle center" in msg or "where to give" in msg or "where can i give" in msg:
        return (
            "You can use the 'Find nearest recycling centre' link I provide after analyzing an image. "
            "It opens Google Maps with nearby e-waste recycling or collection centres. "
            "You can also search in Google Maps for 'e-waste recycling centre' or 'battery recycling' in your city."
        )

    # 10) If we have a last detected item, use its disposal rules
    if last_class and _disposal_rules and last_class in _disposal_rules:
        rules = _disposal_rules[last_class]
        name = last_name or rules.get("display_name", last_class)
        steps = rules.get("disposal_steps", [])
        hazards = rules.get("hazards", "")
        tips = rules.get("tips", "")

        # User asking how to dispose / what to do with "this"
        if any(word in msg for word in ["how", "dispose", "throw", "recycle", "get rid", "what should i do"]):
            response = f"For <b>{name}</b>, you should dispose it as follows:<br><ul>"
            for s in steps:
                response += f"<li>{s}</li>"
            response += "</ul>"
            if hazards:
                response += f"<br><b>Hazards:</b> {hazards}"
            if tips:
                response += f"<br><b>Tips:</b> {tips}"
            return response

        # User asking if it is safe / harmful / dangerous
        if any(word in msg for word in ["safe", "harmful", "dangerous", "risk", "toxic"]):
            response = f"<b>{name}</b> is considered e-waste. "
            if hazards:
                response += f"Main hazards: {hazards} "
            response += "So please do not throw it in normal dustbin. Use an authorised e-waste centre."
            return response

        # User asking "what is this" after detection
        if "what is this" in msg or "what item" in msg or "what product" in msg:
            return f"This item was detected as <b>{name}</b>, which belongs to the category: {rules.get('category', 'E-waste')}."

        # Generic fallback using item info
        response = f"You are asking about <b>{name}</b>. "
        if steps:
            response += "Here is a short summary of how to dispose it:<br><ul>"
            for s in steps[:3]:
                response += f"<li>{s}</li>"
            response += "</ul>"
        else:
            response += "It should be treated as e-waste and handed over to an authorised recycler."
        return response

    # 11) Final fallback
    # If user says something kind of related but not very clear
    if any(word in msg for word in ["waste", "e-waste", "electronic", "battery", "mobile", "laptop", "tv",
                                    "television", "printer", "microwave", "washing machine", "pcb"]):
        return (
            "I may not fully understand the exact question, but I can help with e-waste disposal. "
            "Try asking things like:<br>"
            "- How to dispose this item?<br>"
            "- Is it safe to throw this in the dustbin?<br>"
            "- Why is e-waste dangerous?<br>"
            "Also, you can upload an image if you want me to detect a specific product."
        )

    # Completely generic fallback (still polite)
    return (
        "Sorry, I am mainly designed to talk about e-waste and electronic items. "
        "Please upload an image of an electronic product (like a battery, mobile, printer, TV, etc.) "
        "and then ask me how to dispose it safely. "
        "For other kinds of questions, you can ask my elder brother <b>ChatGPT</b> 😊."
    )


@app.route("/chat", methods=["POST"])
def chat():
    load_assets()  # ensures _disposal_rules is loaded

    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    last_class = data.get("last_class")
    last_name = data.get("last_name")

    if not message:
        return jsonify({"error": "Empty message"}), 400

    reply = generate_chat_reply(message, last_class=last_class, last_name=last_name)
    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)
