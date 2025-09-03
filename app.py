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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))  

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
                "dairy": [
                    {"name": "milk", "price": 3.99, "brands": ["Generic", "Organic Valley", "Horizon"]},
                    {"name": "cheese", "price": 4.50, "brands": ["Kraft", "Sargento", "Generic"]},
                    {"name": "yogurt", "price": 1.25, "brands": ["Chobani", "Yoplait", "Generic"]},
                    {"name": "butter", "price": 3.25, "brands": ["Land O Lakes", "Generic"]},
                    {"name": "eggs", "price": 2.99, "brands": ["Generic", "Organic", "Free Range"]}
                ],
                "produce": [
                    {"name": "apples", "price": 1.99, "brands": ["Generic", "Organic"], "types": ["Red", "Green", "Gala"]},
                    {"name": "bananas", "price": 0.59, "brands": ["Chiquita", "Dole", "Generic"]},
                    {"name": "oranges", "price": 1.29, "brands": ["Generic", "Organic"]},
                    {"name": "lettuce", "price": 1.99, "brands": ["Generic", "Organic"]},
                    {"name": "tomatoes", "price": 2.49, "brands": ["Generic", "Organic", "Vine-Ripened"]},
                    {"name": "carrots", "price": 1.19, "brands": ["Generic", "Organic"]}
                ],
                "bakery": [
                    {"name": "bread", "price": 2.99, "brands": ["Wonder", "Sara Lee", "Generic"]},
                    {"name": "bagels", "price": 3.49, "brands": ["Thomas", "Generic"]},
                    {"name": "croissants", "price": 4.99, "brands": ["Generic"]},
                    {"name": "muffins", "price": 3.99, "brands": ["Generic"]}
                ],
                "meat": [
                    {"name": "chicken", "price": 5.99, "brands": ["Tyson", "Perdue", "Generic"]},
                    {"name": "beef", "price": 7.99, "brands": ["Generic", "Organic"]},
                    {"name": "fish", "price": 8.99, "brands": ["Generic", "Farmed", "Wild"]},
                    {"name": "pork", "price": 6.49, "brands": ["Generic", "Organic"]}
                ],
                "snacks": [
                    {"name": "chips", "price": 2.99, "brands": ["Lays", "Doritos", "Generic"]},
                    {"name": "cookies", "price": 3.49, "brands": ["Oreo", "Chips Ahoy", "Generic"]},
                    {"name": "crackers", "price": 2.79, "brands": ["Ritz", "Generic"]},
                    {"name": "popcorn", "price": 1.99, "brands": ["Orville", "Generic"]}
                ],
                "beverages": [
                    {"name": "water", "price": 0.99, "brands": ["Dasani", "Aquafina", "Generic"]},
                    {"name": "soda", "price": 1.99, "brands": ["Coca-Cola", "Pepsi", "Generic"]},
                    {"name": "juice", "price": 3.49, "brands": ["Tropicana", "Simply", "Generic"]},
                    {"name": "coffee", "price": 5.99, "brands": ["Folgers", "Maxwell House", "Generic"]},
                    {"name": "tea", "price": 3.29, "brands": ["Lipton", "Generic"]}
                ],
                "frozen": [
                    {"name": "ice cream", "price": 4.99, "brands": ["Ben & Jerry's", "Breyers", "Generic"]},
                    {"name": "frozen pizza", "price": 6.99, "brands": ["DiGiorno", "Tombstone", "Generic"]},
                    {"name": "frozen vegetables", "price": 2.99, "brands": ["Birds Eye", "Generic"]}
                ],
                "household": [
                    {"name": "paper towels", "price": 4.99, "brands": ["Bounty", "Generic"]},
                    {"name": "toilet paper", "price": 5.99, "brands": ["Charmin", "Generic"]},
                    {"name": "cleaning supplies", "price": 3.99, "brands": ["Clorox", "Lysol", "Generic"]}
                ]
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
            },
            "sales": {
                "current": [
                    {"item": "milk", "discount": 0.5, "until": "2023-12-31"},
                    {"item": "bread", "discount": 0.3, "until": "2023-12-25"}
                ]
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
    
    # Multilingual support (basic)
    multilingual_keywords = {
        "add": ["add", "ajouter", "añadir", "hinzufügen", "添加", "追加"],
        "remove": ["remove", "supprimer", "eliminar", "entfernen", "移除", "削除"],
        "show": ["show", "afficher", "mostrar", "zeigen", "显示", "表示"],
        "find": ["find", "trouver", "encontrar", "finden", "查找", "探す"],
        "suggest": ["suggest", "suggerer", "sugerir", "vorschlagen", "建议", "提案"]
    }
    
    # Check for multilingual commands
    intent = "unknown"
    for intent_key, keywords in multilingual_keywords.items():
        if any(keyword in c for keyword in keywords):
            intent = intent_key
            break
    
    # If no multilingual match, try English
    if intent == "unknown":
        if "add" in c or "buy" in c or "need" in c or "want" in c or "get" in c:
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
    
    # Extract quantity
    qty = parse_quantity(c)
    
    # Extract item with better matching
    item = None
    brand = None
    item_type = None
    
    # First try exact matches with products
    for category, products in shopping_data['products'].items():
        for product in products:
            product_name = product['name'] if isinstance(product, dict) else product
            if product_name in c:
                item = product_name
                # Try to extract brand if available
                if isinstance(product, dict) and 'brands' in product:
                    for brand_option in product['brands']:
                        if brand_option.lower() in c:
                            brand = brand_option
                # Try to extract type if available
                if isinstance(product, dict) and 'types' in product:
                    for type_option in product['types']:
                        if type_option.lower() in c:
                            item_type = type_option
                break
        if item:
            break
    
    # If no exact match, try fuzzy matching
    if not item:
        command_words = ["add", "remove", "delete", "buy", "get", "need", "want", 
                         "show", "list", "find", "search", "for", "my", "the", "shopping", "list"]
        words = [word for word in c.split() if word not in command_words and word not in NUMBER_WORDS]
        if words:
            item = " ".join(words)
    
    # Extract price filter
    price_filter = None
    price_patterns = [
        r"(under|below|less than)\s*\$?\s*([\d\.]+)",
        r"\$?([\d\.]+)\s*(and|\-|to)\s*\$?([\d\.]+)",
        r"\$?([\d\.]+)\s*(or\s*)?(lower|less|cheaper)"
    ]
    
    for pattern in price_patterns:
        m = re.search(pattern, c)
        if m:
            if "under" in pattern or "below" in pattern or "less than" in pattern:
                price_filter = {"max": float(m.group(2))}
            elif "and" in pattern or "-" in pattern or "to" in pattern:
                price_filter = {"min": float(m.group(1)), "max": float(m.group(3))}
            break
    
    # Extract organic preference
    organic = "organic" in c
    
    return intent, item, qty, price_filter, brand, item_type, organic

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
    
    intent, item, qty, price_filter, brand, item_type, organic = parse_command(command)
    
    if intent == "add" and item:
        return add_item(item, qty, brand, item_type, organic)
    elif intent == "remove" and item:
        return remove_item(item)
    elif intent == "show":
        return get_shopping_list()
    elif intent == "find" and item:
        return search_items(item, price_filter, brand, item_type, organic)
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

def add_item(item_name, quantity, brand=None, item_type=None, organic=False):
    init_user_session()
    user_id = session['user_id']
    
    if not item_name:
        return "What would you like to add to your shopping list?"
    
    # Find category and product details
    category = "uncategorized"
    product_details = {}
    
    for cat, products in shopping_data['products'].items():
        for product in products:
            product_name = product['name'] if isinstance(product, dict) else product
            if product_name == item_name:
                category = cat
                if isinstance(product, dict):
                    product_details = product.copy()
                break
        if category != "uncategorized":
            break
    
    # Check if item is already in list
    shopping_list = shopping_data['users'][user_id]['shopping_list']
    for item in shopping_list:
        if (item['name'] == item_name and 
            item.get('brand') == brand and 
            item.get('type') == item_type and
            item.get('organic') == organic):
            item['quantity'] += quantity
            save_shopping_data()
            response = f"Updated quantity of {format_item_name(item)} to {item['quantity']}."
            threading.Thread(target=text_to_speech, args=(response,)).start()
            return response
    
    # Add new item
    new_item = {
        'name': item_name,
        'quantity': quantity,
        'category': category,
        'added_on': datetime.now().isoformat(),
        'brand': brand,
        'type': item_type,
        'organic': organic
    }
    
    # Add price if available
    if 'price' in product_details:
        new_item['price'] = product_details['price']
    
    shopping_data['users'][user_id]['shopping_list'].append(new_item)
    
    # Add to history
    history_item = new_item.copy()
    history_item['added_on'] = datetime.now().isoformat()
    shopping_data['users'][user_id]['history'].append(history_item)
    
    save_shopping_data()
    
    # Generate suggestions
    suggestions = generate_suggestions(item_name)
    
    # Check for sales
    sale_info = check_for_sales(item_name)
    
    response = f"Added {quantity} {format_item_name(new_item)} to your shopping list."
    if sale_info:
        response += f" {sale_info}"
    if suggestions:
        response += f" You might also need: {', '.join(suggestions[:3])}."
    
    threading.Thread(target=text_to_speech, args=(response,)).start()
    
    return response

def format_item_name(item):
    name_parts = []
    if item.get('organic'):
        name_parts.append("organic")
    if item.get('brand'):
        name_parts.append(item['brand'])
    if item.get('type'):
        name_parts.append(item['type'])
    name_parts.append(item['name'])
    return " ".join(name_parts)

def check_for_sales(item_name):
    for sale in shopping_data.get('sales', {}).get('current', []):
        if sale['item'] == item_name:
            return f"On sale: {sale['discount']*100}% off until {sale['until']}!"
    return None

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

def search_items(item_name, price_filter=None, brand=None, item_type=None, organic=False):
    if not item_name:
        return "What would you like me to search for?"
    
    results = []
    for category, products in shopping_data['products'].items():
        for product in products:
            product_name = product['name'] if isinstance(product, dict) else product
            
            # Check if product matches search criteria
            matches = item_name in product_name
            if brand and isinstance(product, dict) and 'brands' in product:
                matches = matches and brand in product['brands']
            if item_type and isinstance(product, dict) and 'types' in product:
                matches = matches and item_type in product['types']
            if organic:
                matches = matches and "organic" in product_name.lower()
            
            # Check price filter
            if matches and price_filter and isinstance(product, dict) and 'price' in product:
                price = product['price']
                if 'max' in price_filter and price > price_filter['max']:
                    matches = False
                if 'min' in price_filter and price < price_filter['min']:
                    matches = False
            
            if matches:
                result = product_name
                if isinstance(product, dict) and 'price' in product:
                    result += f" (${product['price']})"
                results.append(result)
    
    if results:
        response = f"I found {len(results)} items: {', '.join(results[:5])}."
        if len(results) > 5:
            response += f" And {len(results) - 5} more."
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
    
    # Substitute suggestions
    for product, substitutes in shopping_data['substitutes'].items():
        if product in item_name:
            suggestions.extend(substitutes)
    
    # Category-based suggestions
    user_categories = set()
    for item in shopping_data['users'][user_id]['shopping_list']:
        user_categories.add(item['category'])
    
    for category in user_categories:
        if category in shopping_data['products']:
            category_items = [item['name'] if isinstance(item, dict) else item 
                             for item in shopping_data['products'][category]]
            suggestions.extend(random.sample(category_items, min(2, len(category_items))))
    
    # Seasonal suggestions
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
    
    # History-based suggestions (items frequently bought together)
    history = shopping_data['users'][user_id].get('history', [])
    if history:
        # Simple algorithm: suggest items that were often added around the same time
        recent_items = [item['name'] for item in history[-5:]] if len(history) >= 5 else []
        suggestions.extend(recent_items)
    
    # Sales suggestions
    for sale in shopping_data.get('sales', {}).get('current', []):
        suggestions.append(sale['item'] + " (on sale!)")
    
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