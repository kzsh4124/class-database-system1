import secrets
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import pymongo
from dataclasses import dataclass
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import xmltodict
from typing import Optional

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
    _id: Optional[str] = None
    isbn: Optional[str] = None
    name: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[str] = None
    publisher: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[str] = None  # 'inStock' or 'lending' or 'reading'
    lend_to: Optional[str] = None # User_id of the user who is borrowing the book


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
    user_data = db.users.find_one({"_id": ObjectId(id)})
    
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
        return redirect(url_for('index'))
    else:
        #Provide error message for duplicate username
        return render_template('register_user.html', msg='ユーザ名がすでに存在します。別の名前を入力してください。')

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
        return redirect(url_for('index'))
    else:
        return render_template('login.html', error="Invalid username or password.")


# 検索システム
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
    
# ユーザ情報
@app.route('/user/<user_id>', methods=['GET'])
def user_books(user_id):
    # Check user's access right
    if not ObjectId.is_valid(user_id):
        login_user_id = session['user_id'] if session.get('user_id') else None
        return render_template('not_found.html', user_id=login_user_id)

    # Connect to the MongoDB and get the database instance
    db = create_mongodb_connection()

    # Get user's information
    user = get_user_from_id(user_id, db)
    if user is None:
        login_user_id = session['user_id'] if session.get('user_id') else None
        return render_template('not_found.html', user_id=login_user_id)

    # If not logged-in user and user.open is False, show error
    if not user.open and (not 'user_id' in session or session['user_id'] != user_id):
        login_user_id = session['user_id'] if session.get('user_id') else None
        return render_template('not_found.html', user_id=login_user_id)

    book_name = request.args.get('book_name', None)
    query = {'user_id': ObjectId(user_id)}
    if book_name:
        query['name'] = book_name
    books = list(db.books.find(query))

    return render_template('user_books.html', user=user, books=books)

# 本の情報
@app.route('/book/<book_id>', methods=['GET'])
def book_info_handler(book_id):

    db = create_mongodb_connection()

    book_data = db.books.find_one({"_id": ObjectId(book_id)})

    if book_data is None:
        user_id = session['user_id'] if session.get('user_id') else None
        return render_template('not_found.html', user_id=user_id)

    owner_data = db.users.find_one({"_id": ObjectId(book_data['user_id'])})
    if owner_data:
        book_data['owner_name'] = owner_data['name']

    return render_template('book_info.html', book=book_data)

# 登録システム
@app.route("/book/register", methods=["GET"])
def get_register():
    isbn = request.args.get("isbn")
    book = None

    if isbn:
        url = f"http://iss.ndl.go.jp/api/sru?operation=searchRetrieve&query=isbn={isbn}"
        response = requests.get(url)
        xml_data = xmltodict.parse(response.content)
        records = xml_data["searchRetrieveResponse"]["records"]

        if records is not None:
            record_data = records["record"][0]["recordData"]["srw_dc:dc"]

            book = {
                "isbn": isbn,
                "name": record_data.get("dc:title"),
                "author": record_data.get("dc:creator"),
                "publish_date": record_data.get("dc:date"),
                "publisher": record_data.get("dc:publisher"),
            }

    if is_logged_in():
        return render_template("register.html", book=book)
    else:
        return redirect("/login")

@app.route("/book/register", methods=["POST"])
def post_register():
    if not is_logged_in():
        return redirect("/login")

    isbn = request.form.get("isbn")
    name = request.form.get("name")
    author = request.form.get("author")
    publish_date = request.form.get("publish_date")
    publisher = request.form.get("publisher")

    new_book = {
        "isbn": isbn,
        "name": name,
        "author": author,
        "publish_date": publish_date,
        "publisher": publisher,
        "user_id": session["user_id"],
        "status": "inStock",
        "lend_to": None
    }
    
    db = create_mongodb_connection()
    db.books.insert_one(new_book)
    return redirect("/")

# 本の更新
# TODO: Noneが出ないようにする必要あるかも
# TODO: /not_foundはないので修正
@app.route('/book/<book_id>/update', methods=['GET'])
def update(book_id):
    if not is_logged_in():
        return redirect('/login')
    
    db = create_mongodb_connection()
    user_id = session.get('user_id')

    book = db.books.find_one({"_id": ObjectId(book_id)})
    
    if book is None or book['user_id'] != user_id:
        # Return the not_found.html template directly
        return render_template('not_found.html', user_id=user_id)

    book_obj = Book(
        _id=str(book['_id']),
        isbn=book['isbn'],
        name=book['name'],
        author=book['author'],
        publish_date=book['publish_date'],
        publisher=book['publisher'],
        user_id=book['user_id'],
        status=book['status'],
        lend_to=book.get('lend_to')
    )
    return render_template('update.html', book=book_obj)

# TODO: url for を直す必要があるかも
@app.route('/book/<book_id>/update', methods=['POST'])
def post_update(book_id):
    if not is_logged_in():
        return redirect('/login')
    
    db = create_mongodb_connection()
    user_id = session.get('user_id')

    book = db.books.find_one({"_id": ObjectId(book_id)})
    
    if book is None or book['user_id'] != user_id:
        return redirect('/not_found')

    status = request.form.get('status', book['status'])
    isbn = request.form.get('isbn', book['isbn'])
    name = request.form.get('name', book['name'])
    author = request.form.get('author', book['author'])
    publish_date = request.form.get('publish_date', book['publish_date'])
    publisher = request.form.get('publisher', book['publisher'])

    db.books.update_one({"_id": ObjectId(book_id)}, {"$set": {
        "status": status, 
        "isbn": isbn,
        "name": name,
        "author": author,
        "publish_date": publish_date,
        "publisher": publisher
    }})

    return redirect(url_for('book_info', book_id=book_id))
if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port='11047')