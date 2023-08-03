import secrets
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import pymongo
from dataclasses import dataclass
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Utility Classes
@dataclass
class User:
    _id: str
    name: str
    password: str
    open: bool  # Whether the user's collection is public
    lend: bool  # Whether lending is allowed 

@dataclass
class Book:
    _id: str
    isbn: str
    name: str
    author: str
    publish_date: str
    publisher: str
    user_id: str
    status: str  # "reading"|"lending"|"inStock"
    lend_to: str  # id(user_id) | None

# Utility functions
def create_mongodb_connection():
    user = 's2111609'
    pwd = 'IzN4LS9k'
    client =pymongo.MongoClient('mongodb://'+user+':'+pwd+'@dbs1.slis.tsukuba.ac.jp:27018')
    db = client[user]
    return db

def is_logged_in():
    return 'user_id' in session

def get_user_from_id(id, db):
    user_data = db.users.find_one({"_id": id})
    
    if user_data is None:
        return None

    return User(
        _id=user_data['_id'],
        name=user_data['name'],
        password=user_data['password'],
        open=user_data['open'],
        lend=user_data['lend']
    )

# endpoints
@app.route('/')
def index():
    if is_logged_in():
        db = create_mongodb_connection()
        user = get_user_from_id(session['user_id'], db)
        books = db.books.find({'user_id': user._id})
        requests = db.requests.find({'owner_user_id': user._id})
        lending = db.books.find({'status': 'lending', 'user_id': user._id})
        return render_template('dashboard.html', books=books, requests=requests, lending=lending)
    else:
        return render_template('index.html')

# 認証周り
@app.route('/user/register', methods=['GET'])
def register():
    return render_template('register_user.html')
    
@app.route('/user/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    open = 'open' in request.form
    lend = 'lend' in request.form
    
    db = create_mongodb_connection()

    # Check if username already exists
    existing_user = db.users.find_one({'name': username})

    if existing_user is None:
        hash_pass = generate_password_hash(password, method='sha256')  
        user_data = {
            'name': username,
            'password': hash_pass,
            'open': open,
            'lend': lend
        }
        db.users.insert_one(user_data)
        user = db.users.find_one({'name': username})
        session['user_id'] = str(user['_id'])

        #Successful registration, redirect to dashboard
        return redirect(url_for('dashboard'))
    else:
        #Provide error message for duplicate username
        return render_template('register_err.html', msg='The provided username already exists.')

@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    name = request.form.get('user_name')
    password = request.form.get('password')

    db = create_mongodb_connection()
    user = db.users.find_one({"name": name})

    if user and check_password_hash(user["password"], password):
        session['user_id'] = str(user["_id"])
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Invalid username or password.")



@app.route("/search", methods=["GET"])
def search():
    return render_template("search.html")

@app.route('/result', methods=['POST'])
def result():
    target = request.form['target']  # 'user' or 'book'
    name = request.form.get('name', '')
    isbn = request.form.get('isbn', '')

    db = create_mongodb_connection()

    if target == 'user':
        # Searching for users
        users = db.users.find({"name": {"$regex": name}})

        user_results = []
        for user in users:
            user_results.append(User(
                _id=user['_id'],
                name=user['name'],
                password=user['password'],
                open=user['open'],
                lend=user['lend']
            ))
        return render_template('result_user.html', users=user_results)    

    elif target == 'book':
        # Searching for books
        query = {}

        if isbn:
            query['isbn'] = {"$regex": isbn}
        if name:
            query['name'] = {"$regex": name}

        books = db.books.find(query)

        book_results = []
        for book in books:
            owner_user = get_user_from_id(book['user_id'], db)
            book_results.append({
                "_id": str(book['_id']),
                "isbn": book['isbn'],
                "name": book['name'],
                "author": book['author'],
                "publish_date": book['publish_date'],
                "publisher": book['publisher'],
                "user_name": owner_user.name if owner_user else None,
            })
        return render_template('result_book.html', books=book_results)

    else:
        return jsonify({"message": "target must be 'user' or 'book'."})
    




if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port='11047')