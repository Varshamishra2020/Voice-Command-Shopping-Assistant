import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import speech_recognition as sr
from gtts import gTTS
import playsound
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import random

# Download NLTK data
nltk.download('punkt')
nltk.download('stopwords')

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Initialize shopping data
def init_shopping_data():
    data_file = 'data/shopping_data.json'
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
        os.makedirs('data', exist_ok=True)
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=4)
    
    with open(data_file, 'r') as f:
        return json.load(f)

shopping_data = init_shopping_data()

# Initialize user session
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

# Speech recognition function
def recognize_speech():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    with microphone as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
    
    try:
        text = recognizer.recognize_google(audio)
        print(f"Recognized: {text}")
        return text.lower()
    except sr.UnknownValueError:
        return "Sorry, I didn't understand that."
    except sr.RequestError:
        return "Sorry, there was an error with the speech service."
    except sr.WaitTimeoutError:
        return "Sorry, I didn't hear anything."

# Text-to-speech function
def text_to_speech(text):
    tts = gTTS(text=text, lang='en')
    filename = f"static/audio/{int(time.time())}.mp3"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    tts.save(filename)
    playsound.playsound(filename)
    os.remove(filename)  # Clean up after playing

# NLP processing for voice commands
def process_command(command):
    tokens = word_tokenize(command)
    filtered_tokens = [word for word in tokens if word not in stopwords.words('english')]
    
    # Check for add command
    if any(word in filtered_tokens for word in ['add', 'need', 'want', 'buy', 'get']):
        return add_item(command)
    
    # Check for remove command
    elif any(word in filtered_tokens for word in ['remove', 'delete', 'drop']):
        return remove_item(command)
    
    # Check for search command
    elif any(word in filtered_tokens for word in ['find', 'search', 'look']):
        return search_items(command)
    
    # Check for list command
    elif any(word in filtered_tokens for word in ['list', 'show', 'what']):
        return get_shopping_list()
    
    else:
        return "I'm not sure what you want to do. Try saying 'add milk' or 'remove eggs'."

# Add item to shopping list
def add_item(command):
    init_user_session()
    user_id = session['user_id']
    
    # Extract item and quantity from command
    tokens = word_tokenize(command)
    quantity = 1
    item_words = []
    
    # Look for quantity indicators
    for i, token in enumerate(tokens):
        if token.isdigit():
            quantity = int(token)
        elif token in ['a', 'an']:
            quantity = 1
        else:
            item_words.append(token)
    
    # Remove command words
    command_words = ['add', 'need', 'want', 'buy', 'get', 'to', 'my', 'shopping', 'list']
    item_name = ' '.join([word for word in item_words if word not in command_words])
    
    if not item_name:
        return "What would you like to add to your shopping list?"
    
    # Categorize the item
    category = "uncategorized"
    for cat, items in shopping_data['products'].items():
        if any(product in item_name for product in items):
            category = cat
            break
    
    # Add to shopping list
    new_item = {
        'name': item_name,
        'quantity': quantity,
        'category': category,
        'added_on': datetime.now().isoformat()
    }
    
    shopping_data['users'][user_id]['shopping_list'].append(new_item)
    save_shopping_data()
    
    # Generate smart suggestions
    suggestions = generate_suggestions(item_name)
    
    response = f"Added {quantity} {item_name} to your shopping list."
    if suggestions:
        response += f" You might also need: {', '.join(suggestions[:3])}."
    
    return response

# Remove item from shopping list
def remove_item(command):
    init_user_session()
    user_id = session['user_id']
    
    # Extract item from command
    tokens = word_tokenize(command)
    command_words = ['remove', 'delete', 'drop', 'from', 'my', 'shopping', 'list']
    item_words = [word for word in tokens if word not in command_words]
    item_name = ' '.join(item_words)
    
    if not item_name:
        return "What would you like to remove from your shopping list?"
    
    # Find and remove the item
    shopping_list = shopping_data['users'][user_id]['shopping_list']
    removed = False
    
    for i, item in enumerate(shopping_list):
        if item_name in item['name']:
            shopping_list.pop(i)
            removed = True
            break
    
    if removed:
        save_shopping_data()
        return f"Removed {item_name} from your shopping list."
    else:
        return f"I couldn't find {item_name} in your shopping list."

# Search for items
def search_items(command):
    # Extract search terms from command
    tokens = word_tokenize(command)
    command_words = ['find', 'search', 'for', 'look', 'me']
    search_terms = [word for word in tokens if word not in command_words]
    
    if not search_terms:
        return "What would you like me to search for?"
    
    # Simple search implementation
    results = []
    for category, items in shopping_data['products'].items():
        for item in items:
            if any(term in item for term in search_terms):
                results.append(item)
    
    if results:
        return f"I found these items: {', '.join(results[:5])}."
    else:
        return "I couldn't find any items matching your search."

# Get shopping list
def get_shopping_list():
    init_user_session()
    user_id = session['user_id']
    
    shopping_list = shopping_data['users'][user_id]['shopping_list']
    
    if not shopping_list:
        return "Your shopping list is empty."
    
    # Group by category
    categorized = {}
    for item in shopping_list:
        category = item['category']
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(f"{item['quantity']} {item['name']}")
    
    response = "Here's your shopping list: "
    for category, items in categorized.items():
        response += f"{category}: {', '.join(items)}. "
    
    return response

# Generate smart suggestions
def generate_suggestions(item_name):
    init_user_session()
    user_id = session['user_id']
    
    suggestions = []
    
    # Suggest substitutes
    for product, substitutes in shopping_data['substitutes'].items():
        if product in item_name:
            suggestions.extend(substitutes)
    
    # Suggest items from the same category
    for category, items in shopping_data['products'].items():
        if any(product in item_name for product in items):
            # Add a few random items from the same category
            suggestions.extend(random.sample(items, min(2, len(items))))
    
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
    
    # Remove duplicates and the original item
    suggestions = list(set(suggestions))
    if item_name in suggestions:
        suggestions.remove(item_name)
    
    return suggestions[:5]  # Return top 5 suggestions

# Flask routes
@app.route('/')
def index():
    init_user_session()
    return render_template('index.html')

@app.route('/voice-command', methods=['POST'])
def voice_command():
    command = recognize_speech()
    if command.startswith("Sorry"):
        return jsonify({'response': command})
    
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
def clear_list():
    init_user_session()
    user_id = session['user_id']
    shopping_data['users'][user_id]['shopping_list'] = []
    save_shopping_data()
    return jsonify({'response': "Shopping list cleared."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)