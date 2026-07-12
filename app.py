from flask import Flask, render_template, request, redirect, session
import os
import classify
from PIL import Image
import numpy as np
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import bcrypt
from datetime import datetime

app = Flask(__name__)

# ==========================
# CONFIG
# ==========================

basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'Model.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '1A2bc4s'

db = SQLAlchemy(app)

# ==========================
# DATABASE MODELS
# ==========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('user.id'))
    image = db.Column(db.String(200), nullable=False)
    result = db.Column(db.String(200), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ==========================
# HOME ROUTES
# ==========================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/model')
def model():
    return render_template("model.html")

@app.route('/result')
def result():
    return render_template("result_train.html")

# ==========================
# REGISTER
# ==========================

@app.route('/register', methods=['POST'])
def register():

    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('newPass')
    confirm = request.form.get('confPass')

    # Validation
    if not username or not email or not password or not confirm:
        return render_template("login.html",
                               regError="All fields are required")

    if password != confirm:
        return render_template("login.html",
                               regError="Passwords do not match")

    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'),
                               bcrypt.gensalt())

        new_user = User(
            username=username,
            email=email,
            password=hashed
        )

        db.session.add(new_user)
        db.session.commit()

        # Store success message in session
        session['successMessage'] = "Account created successfully. Please login."

        return redirect('/login')

    except IntegrityError as e:
        db.session.rollback()
        print("ERROR:", e)
        return render_template("login.html",
                               regError="Username or Email already exists")

# ==========================
# LOGIN
# ==========================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'GET':
        successMessage = session.pop('successMessage', None)
        return render_template("login.html",
                               successMessage=successMessage)

    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return render_template("login.html",
                               loginError="Please enter username and password")

    user = User.query.filter_by(username=username).first()

    if not user:
        return render_template("login.html",
                               loginError="User not found")

    if not bcrypt.checkpw(password.encode('utf-8'), user.password):
        return render_template("login.html",
                               loginError="Incorrect password")

    session['logged'] = True
    session['userId'] = user.id

    return redirect('/output')

# ==========================
# LOGOUT
# ==========================

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==========================
# PROFILE
# ==========================

@app.route('/profile')
def profile():

    if 'userId' not in session:
        return redirect('/login')

    user = User.query.get(session['userId'])

    history = History.query.filter_by(userId=session['userId'])\
        .order_by(History.date_created.desc()).all()

    return render_template("profile.html",
                           details=user,
                           history_items=history)

# ==========================
# OUTPUT (SCAN)
# ==========================

@app.route('/output', methods=['GET', 'POST'])
def output():

    if 'userId' not in session:
        return redirect('/login')

    image_path = None
    result = None

    if request.method == 'POST':

        if 'imagefile' not in request.files:
            return redirect('/output')

        image_file = request.files['imagefile']

        if image_file.filename == '':
            return redirect('/output')

        modelNo = int(request.form.get('model'))

        os.makedirs("static/images/test", exist_ok=True)

        save_path = os.path.join("static/images/test", image_file.filename)
        image_file.save(save_path)

        image_path = "/" + save_path

        image = Image.open(save_path)

        prediction = classify.predict(image, modelNo)

        class_names = ['Plain', 'Pothole']

        result = "{} with {:.2f}% Confidence.".format(
            class_names[np.argmax(prediction)],
            100 * np.max(prediction)
        )

        new_history = History(
            userId=session['userId'],
            image=image_path,
            result=result
        )

        db.session.add(new_history)
        db.session.commit()

    return render_template("output.html",
                           result=result,
                           image=image_path)

# ==========================

if __name__ == '__main__':
    app.run(debug=True)