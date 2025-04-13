import os
import time
import sqlite3
import threading
from dotenv import load_dotenv
load_dotenv()
from collections import deque
from functools import wraps
from datetime import datetime
import smtplib

import cv2
import pygame
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, Response, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

from utils.detection import detect_objects

# --- Flask App Config ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key')

# --- Email Alert Config ---
ALERT_EMAIL = os.environ.get('ALERT_EMAIL', 'your_email@gmail.com')
ALERT_PASSWORD = os.environ.get('ALERT_PASSWORD', 'your_app_password')
TO_EMAIL = os.environ.get('TO_EMAIL', 'recipient_email@gmail.com')
last_email_time = 0  # For cooldown

# --- Siren Setup ---
pygame.mixer.init()
SIREN_PATH = os.path.join('static', 'audio', 'siren.mp3')
siren_playing = False
siren_lock = threading.Lock()

def play_siren():
    global siren_playing
    with siren_lock:
        if not siren_playing:
            try:
                pygame.mixer.music.load(SIREN_PATH)
                pygame.mixer.music.play(-1)
                siren_playing = True
                print("🔊 Siren started looping.")
            except Exception as e:
                print("❌ Failed to play siren:", e)

def stop_siren():
    global siren_playing
    with siren_lock:
        if siren_playing:
            pygame.mixer.music.stop()
            siren_playing = False
            print("🔇 Siren stopped.")

# --- SQLite DB setup ---
DATABASE = os.path.join(app.root_path, 'users.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    db.commit()

with app.app_context():
    init_db()

# --- Auth Decorator ---
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

# --- Routes ---
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('login'))
    return redirect(url_for('register'))

@app.route('/dashboard')
@login_required
def dashboard():
    latest = recent_counts[-1]['count'] if recent_counts else 0
    return render_template('dashboard.html', count=latest)

@app.route('/crowd_data')
@login_required
def crowd_data_route():
    return jsonify(list(recent_counts)[-10:])

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(
        gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        error = None

        if not username or not password:
            error = 'Username and password are required.'
        elif db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone():
            error = f'User "{username}" already exists.'

        if error is None:
            db.execute(
                'INSERT INTO user (username, password_hash) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))

        flash(error, 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password.', 'error')
        else:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/trigger_alert', methods=['POST'])
@login_required
def trigger_alert():
    send_email_alert(count=99)
    threading.Thread(target=play_siren).start()
    flash("🚨 Demo alert email and siren triggered!", "success")
    return redirect(url_for('dashboard'))

# --- Email Alert Function ---
def send_email_alert(count):
    global last_email_time
    now = time.time()
    if now - last_email_time < 300:
        return
    subject = "🚨 Crowd Alert Notification"
    body = f"⚠ High crowd density detected: {count} people at {datetime.now().strftime('%H:%M:%S')}"
    msg = f"Subject: {subject}\n\n{body}"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(ALERT_EMAIL, ALERT_PASSWORD)
            server.sendmail(ALERT_EMAIL, TO_EMAIL, msg)
            print("✅ Email alert sent.")
            last_email_time = now
    except Exception as e:
        print("❌ Email sending failed:", e)

# --- Video Feed Logic ---
cap = cv2.VideoCapture(0)
recent_counts = deque(maxlen=100)

def gen_frames():
    total_area_sqft =8
    min_space_per_person = 4

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame, person_count = detect_objects(frame)

        density = person_count / total_area_sqft
        allowed_people = total_area_sqft // min_space_per_person

        cv2.putText(frame, f"People: {person_count}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Density: {density:.2f} per sq ft", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 215, 0), 2)
        cv2.putText(frame, f"Max Capacity: {allowed_people} people", (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 255, 255), 2)

        if person_count > allowed_people:
            cv2.putText(frame, 'OVERCROWDING DETECTED!', (20, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            send_email_alert(person_count)
            threading.Thread(target=play_siren).start()
        else:
            threading.Thread(target=stop_siren).start()

        recent_counts.append({
            'time': int(time.time()),
            'count': person_count
        })

        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

if __name__ == '__main__':
    app.run(debug=True)
