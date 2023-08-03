import secrets
from flask import Flask, render_template, request, session, redirect, url_for
import pymongo
from dataclasses import dataclass

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

# define endpoint here



if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port='11047')