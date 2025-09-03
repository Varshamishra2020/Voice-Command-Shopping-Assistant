import os
import json
import threading
import time
import io
import re
import wave
import struct
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import speech_recognition as sr
from gtts import gTTS
import playsound
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import random
import base64

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

app = Flask(__name__)
app.secret_key = os.urandom(24)  

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1
}

def init_shopping_data():
    data_file = 'data/shopping_data.json'
    if not os.path.exists('data'):
        os.makedirs('data')
        
    if not os.path.exists(data_file):
        data = {
            "users": {},
            "products": {
                "dairy": ["milk", "cheese", "yogurt", "butter", "eggs"],
                "produce": ["apples", "bananas", "oranges", "lettuce", "tomatoes", "carrots"],
                "bakery": ["bread", "bagels", "croissants", "muffins"],
                "meat": ["chicken", "beef", "fish", "pork"],
                "snacks": ["chips", "cookies", "crackers", "popcorn"],
                "beverages": ["water", "soda", "juice", "coffee", "tea"],
                "frozen": ["ice cream", "frozen pizza", "frozen vegetables"],
                "household": ["paper towels", "toilet paper", "cleaning supplies"]
            },
            "substitutes": {
                "milk": ["almond milk", "soy milk", "oat milk", "coconut milk"],
                "bread": ["whole wheat bread", "rye bread", "gluten-free bread"],
                "butter": ["margarine", "olive oil", "coconut oil"],
                "eggs": ["tofu", "applesauce", "commercial egg replacer"],
                "sugar": ["honey", "maple syrup", "stevia"]
            },
            "seasonal_items": {
                "winter": ["hot chocolate", "soup", "stuffing", "cranberries"],
                "spring": ["asparagus", "strawberries", "spinach", "peas"],
                "summer": ["watermelon", "corn", "berries", "grill supplies"],
                "fall": ["pumpkin", "apples", "squash", "cinnamon"]
            }
        }
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=4)
    
    with open(data_file, 'r') as f:
        return json.load(f)

shopping_data = init_shopping_data()

def init_user_session():
    if 'user_id' not in session:
        session['user_id'] = str(int(time.time() * 1000))
    
    user_id = session['user_id']
    if user_id not in shopping_data['users']:
        shopping_data['users'][user_id] = {
            'shopping_list': [],
            'history': [],
            'preferences': {}
        }
        save_shopping_data()

def save_shopping_data():
    with open('data/shopping_data.json', 'w') as f:
        json.dump(shopping_data, f, indent=4)

def parse_quantity(text):
    m = re.search(r"(\d+)", text)
    if m:
        return int(m.group(1))
    for w, v in NUMBER_WORDS.items():
        if w in text:
            return v
    return 1

def parse_command(command):
    c = command.lower()
    
    qty = parse_quantity(c)
    
    if "add" in c or "buy" in c or "need" in c or "want" in c:
        intent = "add"
    elif "remove" in c or "delete" in c or "drop" in c:
        intent = "remove"
    elif "show" in c or "list" in c or "what's on" in c:
        intent = "show"
    elif "find" in c or "search" in c or "look for" in c:
        intent = "find"
    elif "suggest" in c or "recommend" in c:
        intent = "suggest"
    elif "clear" in c or "empty" in c:
        intent = "clear"
    else:
        intent = "unknown"
    
    item = None
    
    for category, products in shopping_data['products'].items():
        for product in products:
            if product in c:
                item = product
                break
        if item:
            break
    
    if not item:
        command_words = ["add", "remove", "delete", "buy", "get", "need", "want", 
                         "show", "list", "find", "search", "for", "my", "the", "shopping", "list"]
        words = [word for word in c.split() if word not in command_words and word not in NUMBER_WORDS]
        if words:
            item = words[-1]
    
    price_filter = None
    m = re.search(r"(under|below|less than)\s*\$?\s*([\d\.]+)", c)
    if m:
        price_filter = float(m.group(2))
    
    return intent, item, qty, price_filter

def convert_audio_to_wav(audio_data):
    try:
        if isinstance(audio_data, str) and audio_data.startswith('data:audio/webm;base64,'):
            audio_data = audio_data.split(',')[1]
        
        audio_bytes = base64.b64decode(audio_data)

        tmp_input = "temp_input.webm"
        tmp_output = "temp_output.wav"

        with open(tmp_input, "wb") as f:
            f.write(audio_bytes)

        os.system(f"ffmpeg -i {tmp_input} -ar 16000 -ac 1 {tmp_output} -y")

        with open(tmp_output, "rb") as f:
            wav_data = f.read()

        os.remove(tmp_input)
        os.remove(tmp_output)

        return wav_data
    except Exception as e:
        print(f"Audio conversion error: {e}")
        return None

def recognize_speech(audio_data=None):
    recognizer = sr.Recognizer()
    
    try:
        if audio_data:
            try:
                wav_data = convert_audio_to_wav(audio_data)
                if wav_data:
                    with sr.AudioFile(io.BytesIO(wav_data)) as source:
                        audio = recognizer.record(source)
                    text = recognizer.recognize_google(audio)
                    print(f"Recognized: {text}")
                    return text.lower()
            except Exception as e:
                print(f"Audio data processing failed: {e}")
                
                pass
        
        with sr.Microphone() as source:
            print("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening...")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        
        print("Processing speech...")
        text = recognizer.recognize_google(audio)
        print(f"Recognized: {text}")
        return text.lower()
    except sr.WaitTimeoutError:
        return "timeout"
    except sr.UnknownValueError:
        return "unknown"
    except sr.RequestError as e:
        print(f"Speech recognition error: {e}")
        return "error"
    except Exception as e:
        print(f"Speech recognition failed: {e}")
        return "Please check your microphone and try again."

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='en')
        filename = f"audio_{int(time.time())}.mp3"
        os.makedirs('audio', exist_ok=True)
        filepath = os.path.join('audio', filename)
        tts.save(filepath)
        playsound.playsound(filepath)
        threading.Thread(target=cleanup_audio, args=(filepath,)).start()
    except Exception as e:
        print(f"Text-to-speech error: {e}")

def cleanup_audio(filepath):
    time.sleep(2)  
    try:
        os.remove(filepath)
    except:
        pass

def process_command(command):
    if command in ["timeout", "unknown", "error"]:
        return "I didn't catch that. Please try again."
    
    intent, item, qty, price_filter = parse_command(command)
    
    if intent == "add" and item:
        return add_item(item, qty)
    elif intent == "remove" and item:
        return remove_item(item)
    elif intent == "show":
        return get_shopping_list()
    elif intent == "find" and item:
        return search_items(item, price_filter)
    elif intent == "suggest":
        return suggest_items()
    elif intent == "clear":
        return clear_list()
    elif intent == "unknown":
        if any(word in command for word in ["hello", "hi", "hey", "greetings"]):
            return "Hello! How can I help with your shopping list today?"
        
        if any(word in command for word in ["thank", "thanks", "appreciate"]):
            return "You're welcome! Is there anything else you need?"
        
        return "I'm not sure what you want to do. Try saying 'add milk' or 'what's on my list'."
    
    return "I'm not sure what you want to do. Try saying 'add milk' or 'what's on my list'."

def add_item(item_name, quantity):
    init_user_session()
    user_id = session['user_id']
    
    if not item_name:
        return "What would you like to add to your shopping list?"
    
    category = "uncategorized"
    for cat, items in shopping_data['products'].items():
        if item_name in items:
            category = cat
            break
    
    shopping_list = shopping_data['users'][user_id]['shopping_list']
    for item in shopping_list:
        if item['name'] == item_name:
            item['quantity'] += quantity
            save_shopping_data()
            response = f"Updated quantity of {item_name} to {item['quantity']} in your shopping list."
            threading.Thread(target=text_to_speech, args=(response,)).start()
            return response
    
    new_item = {
        'name': item_name,
        'quantity': quantity,
        'category': category,
        'added_on': datetime.now().isoformat()
    }
    
    shopping_data['users'][user_id]['shopping_list'].append(new_item)
    save_shopping_data()
    
    suggestions = generate_suggestions(item_name)
    
    response = f"Added {quantity} {item_name} to your shopping list."
    if suggestions:
        response += f" You might also need: {', '.join(suggestions[:3])}."
    
    threading.Thread(target=text_to_speech, args=(response,)).start()
    
    return response

def remove_item(item_name):
    init_user_session()
    user_id = session['user_id']
    
    if not item_name:
        return "What would you like to remove from your shopping list?"
    
    shopping_list = shopping_data['users'][user_id]['shopping_list']
    removed = False
    removed_item = None
    
    for i, item in enumerate(shopping_list):
        if item_name == item['name']:
            removed_item = shopping_list.pop(i)
            removed = True
            break
    
    if removed:
        save_shopping_data()
        response = f"Removed {removed_item['name']} from your shopping list."
        threading.Thread(target=text_to_speech, args=(response,)).start()
        return response
    else:
        return f"I couldn't find {item_name} in your shopping list."

def search_items(item_name, price_filter=None):
    if not item_name:
        return "What would you like me to search for?"
    
    results = []
    for category, items in shopping_data['products'].items():
        for item in items:
            if item_name in item:
                results.append(item)
    
    if results:
        response = f"I found these items: {', '.join(results[:5])}."
        if price_filter:
            response += f" Filtered to under ${price_filter}."
        return response
    else:
        return "I couldn't find any items matching your search."

def get_shopping_list():
    init_user_session()
    user_id = session['user_id']
    
    shopping_list = shopping_data['users'][user_id]['shopping_list']
    
    if not shopping_list:
        return "Your shopping list is empty."
    
    categorized = {}
    for item in shopping_list:
        category = item['category']
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(f"{item['quantity']} {item['name']}")
    
    response = "Here's your shopping list: "
    for category, items in categorized.items():
        response += f"{category}: {', '.join(items)}. "
    
    threading.Thread(target=text_to_speech, args=(response,)).start()
    
    return response

def suggest_items():
    init_user_session()
    user_id = session['user_id']
    
    history = shopping_data['users'][user_id]['history']
    if not history:
        return "I don't have enough history to make suggestions yet."
    

    recent_items = [item['name'] for item in history[-3:]] if len(history) >= 3 else []
    
    if recent_items:
        response = f"Based on your history, you might need: {', '.join(recent_items)}."
        threading.Thread(target=text_to_speech, args=(response,)).start()
        return response
    else:
        return "I don't have enough history to make suggestions yet."


def clear_list():
    init_user_session()
    user_id = session['user_id']
    shopping_data['users'][user_id]['shopping_list'] = []
    save_shopping_data()
    
    response = "Shopping list cleared."
    threading.Thread(target=text_to_speech, args=(response,)).start()
    
    return response


def generate_suggestions(item_name):
    init_user_session()
    user_id = session['user_id']
    
    suggestions = []
    
    
    for product, substitutes in shopping_data['substitutes'].items():
        if product in item_name:
            suggestions.extend(substitutes)
    
    
    for category, items in shopping_data['products'].items():
        if any(product in item_name for product in items):
            
            suggestions.extend(random.sample(items, min(2, len(items))))
    

    current_month = datetime.now().month
    if current_month in [12, 1, 2]:
        season = "winter"
    elif current_month in [3, 4, 5]:
        season = "spring"
    elif current_month in [6, 7, 8]:
        season = "summer"
    else:
        season = "fall"
    
    suggestions.extend(shopping_data['seasonal_items'][season])
    
    suggestions = list(set(suggestions))
    if item_name in suggestions:
        suggestions.remove(item_name)
    
    return suggestions[:5]  


@app.route('/')
def index():
    init_user_session()
    return render_template('index.html')
@app.route('/voice-command', methods=['POST'])
def voice_command():
    data = request.get_json()

    audio_data = data.get("audio") if data else None

    command = recognize_speech(audio_data)

    response = process_command(command)
    return jsonify({'response': response})

@app.route('/text-command', methods=['POST'])
def text_command():
    data = request.get_json()
    command = data.get('command', '').lower()
    
    if not command:
        return jsonify({'response': "Please provide a command."})
    
    response = process_command(command)
    return jsonify({'response': response})

@app.route('/shopping-list', methods=['GET'])
def get_list():
    init_user_session()
    user_id = session['user_id']
    return jsonify({'shopping_list': shopping_data['users'][user_id]['shopping_list']})

@app.route('/clear-list', methods=['POST'])
def clear_list_route():
    return jsonify({'response': clear_list()})

if __name__ == '__main__':
    if not os.path.exists('audio'):
        os.makedirs('audio')
    if not os.path.exists('data'):
        os.makedirs('data')
    app.run(debug=True, host='0.0.0.0', port=5000)