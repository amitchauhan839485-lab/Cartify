from flask import Flask, render_template, request, redirect, url_for, jsonify
from database import get_db_connection, init_db
import sqlite3
import os
from dotenv import load_dotenv
from groq import Groq
import joblib
sales_model = joblib.load("sales_model.pkl")
# ✅ BERT-based model
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --------------------------
# LOAD ENV
# --------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY not found in .env")

print("GROQ KEY LOADED ✅")

# --------------------------
# GROQ CLIENT
# --------------------------
client = Groq(api_key=GROQ_API_KEY)

# --------------------------
# FLASK APP
# --------------------------
app = Flask(__name__)

# --------------------------
# ML VARIABLES (BERT)
# --------------------------
model = SentenceTransformer('all-mpnet-base-v2')  # 🔥 BERT-based model
product_embeddings = None
product_data = []

# --------------------------
# LOAD ML MODEL
# --------------------------
def load_model():
    global product_data, product_embeddings

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()

    product_data = products

    texts = [
        (p['name'] or '') + " " + (p['description'] or '')
        for p in products
    ]

    if texts:
        product_embeddings = model.encode(texts)
    else:
        product_embeddings = None

# --------------------------
# SMART SEARCH (BERT)
# --------------------------
def smart_search(query):
    global product_embeddings, product_data

    if product_embeddings is None or len(product_embeddings) == 0 or not query:
        return []

    query_embedding = model.encode([query])
    scores = cosine_similarity(query_embedding, product_embeddings)[0]

    ranked = sorted(
        zip(product_data, scores),
        key=lambda x: x[1],
        reverse=True
    )

    # 🔥 slightly higher threshold for BERT
    return [p[0] for p in ranked if p[1] > 0.4]

# --------------------------
# CHATBOT
# --------------------------
def chatbot_reply(user_message):
    try:
        results = smart_search(user_message)
        top_products = results[:5]

        if top_products:
            product_context = "\n".join([
                f"{p['name']} - ₹{p['price']}: {p['description']}"
                for p in top_products
            ])
        else:
            return "Sorry, no matching products found. Try another search."

        prompt = f"""
You are a helpful eCommerce assistant for Cartify.

Use ONLY the products below:

{product_context}

User question: {user_message}

Rules:
- Recommend only from given products
- Be short and clear
- Mention product names
"""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a shopping assistant."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant"
        )

        return chat_completion.choices[0].message.content

    except Exception as e:
        print("Groq Error:", e)
        return "⚠️ AI service unavailable"

# --------------------------
# ROUTES
# --------------------------

@app.route('/')
def home():
    query = request.args.get('q', '').strip().lower()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()

    filtered_products = smart_search(query) if query else products

    return render_template('home.html', products=filtered_products)

# --------------------------
# ADD PRODUCT
# --------------------------
@app.route('/admin/add-product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        try:
            price = float(request.form.get("price"))
        except:
            return "Invalid price", 400

        image_url = request.form.get("image_url", "").strip()
        if not image_url:
            image_url = "https://via.placeholder.com/150"

        if not name:
            return "Name is required", 400

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO products (name, description, price, image_url) VALUES (?, ?, ?, ?)',
            (name, description, price, image_url)
        )
        conn.commit()
        conn.close()

        load_model()  # refresh ML model

        return redirect(url_for('home'))

    return render_template('add_product.html')

# --------------------------
# SEARCH
# --------------------------
@app.route('/search')
def search():
    query = request.args.get('q', '').strip().lower()

    if not query:
        return redirect(url_for('home'))

    filtered_products = smart_search(query)

    return render_template('search_results.html', products=filtered_products, query=query)

# --------------------------
# CHAT API
# --------------------------
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("message")

        if not user_message:
            return jsonify({"reply": "Please type something"}), 400

        reply = chatbot_reply(user_message)

        return jsonify({"reply": reply})

    except Exception as e:
        print("CHAT ERROR:", e)
        return jsonify({"reply": "Error"}), 500
    
#new router for prediction 
@app.route('/predict', methods=['POST'])
def predict():
    print("🔥 API HIT")   # ADD THIS
    data = request.get_json()

    views = float(data['views'])
    price = float(data['price'])
    discount = float(data['discount'])

    prediction = sales_model.predict([[views, price, discount]])

    return jsonify({
        "predicted_sales": int(prediction[0])
    })
@app.route('/sales-predictor')
def sales_predictor():
    return render_template('sales_predictor.html')
# --------------------------
# RUN APP
# --------------------------
if __name__ == '__main__':
    init_db()
    load_model()
    app.run(host="0.0.0.0", port=5000, debug=True)