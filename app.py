from flask import Flask, render_template, request, redirect, url_for, flash, session
import tensorflow as tf
from PIL import Image
import numpy as np
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Load the trained model
model = tf.keras.models.load_model('models/Resnet50_best_model.keras')
# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  role TEXT NOT NULL DEFAULT 'patient',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Create scans table
    c.execute('''CREATE TABLE IF NOT EXISTS scans
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  image_path TEXT NOT NULL,
                  prediction TEXT NOT NULL,
                  confidence REAL NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    # Create default admin user if not exists
    try:
        c.execute('''INSERT INTO users (username, email, password, role)
                    VALUES (?, ?, ?, ?)''',
                  ('admin', 'admin@neuroscan.ai',
                   generate_password_hash('admin123'), 'admin'))
        conn.commit()
        print("Default admin user created successfully!")
    except sqlite3.IntegrityError:
        print("Admin user already exists")

    conn.close()


# Initialize database
init_db()


# Helper function to get database connection
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND role = "patient"',
                          (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))

        flash('Invalid username or password', 'danger')
    return render_template('login.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND role = "admin"',
                          (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('admin_dashboard'))

        flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'danger')
            return render_template('register.html')

        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                       (username, email, generate_password_hash(password), 'patient'))
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'danger')
        finally:
            db.close()

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    scans = db.execute('''SELECT * FROM scans 
                         WHERE user_id = ? 
                         ORDER BY created_at DESC''',
                       (session['user_id'],)).fetchall()

    return render_template('patient_dashboard.html',
                           username=session['username'],
                           scans=scans)


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    db = get_db()
    total_patients = db.execute('SELECT COUNT(*) FROM users WHERE role = "patient"').fetchone()[0]
    total_scans = db.execute('SELECT COUNT(*) FROM scans').fetchone()[0]
    recent_scans = db.execute('''SELECT s.*, u.username 
                                FROM scans s 
                                JOIN users u ON s.user_id = u.id 
                                ORDER BY s.created_at DESC 
                                LIMIT 5''').fetchall()

    return render_template('admin_dashboard.html',
                           username=session['username'],
                           total_patients=total_patients,
                           total_scans=total_scans,
                           recent_scans=recent_scans)


@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('dashboard'))

    try:
        # Save the uploaded file
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        file.save(file_path)

        # Preprocess the image
        img = Image.open(file_path)
        img = img.resize((128, 128))  # Changed from 224x224 to 128x128
        img_array = np.array(img) / 255.0

        # Check if image is grayscale and add channel dimension if needed
        if len(img_array.shape) == 2:  # If grayscale (no channel dimension)
            img_array = np.expand_dims(img_array, axis=-1)  # Add channel dimension
            img_array = np.repeat(img_array, 3, axis=-1)  # Convert to 3-channel (RGB)
        elif img_array.shape[2] == 1:  # If already has channel dim but just 1 channel
            img_array = np.repeat(img_array, 3, axis=-1)  # Convert to 3-channel

        img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension

        # Make prediction
        prediction = model.predict(img_array)
        class_names = ['Non-Demented', 'Very Mild Demented', 'Mild Demented', 'Moderate Demented']
        predicted_class = class_names[np.argmax(prediction)]
        confidence = float(np.max(prediction))

        # Save scan results to database
        db = get_db()
        db.execute('INSERT INTO scans (user_id, image_path, prediction, confidence) VALUES (?, ?, ?, ?)',
                   (session['user_id'], file_path, predicted_class, confidence))
        db.commit()

        flash(f'Scan completed successfully. Result: {predicted_class} (Confidence: {confidence:.2%})', 'success')

    except Exception as e:
        flash(f'Error processing scan: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/admin/add_patient', methods=['GET', 'POST'])
def admin_add_patient():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                       (username, email, generate_password_hash(password), 'patient'))
            db.commit()
            flash('Patient added successfully!', 'success')
            return redirect(url_for('admin_manage_users'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'danger')
        finally:
            db.close()

    return render_template('admin_add_patient.html')


@app.route('/admin/manage_users')
def admin_manage_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    db = get_db()
    patients = db.execute('''
        SELECT u.*, COUNT(s.id) as scan_count 
        FROM users u 
        LEFT JOIN scans s ON u.id = s.user_id 
        WHERE u.role = 'patient' 
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''').fetchall()

    return render_template('admin_manage_users.html', patients=patients)


@app.route('/admin/delete_user/<int:user_id>')
def admin_delete_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    db = get_db()
    try:
        # Delete user's scans first
        db.execute('DELETE FROM scans WHERE user_id = ?', (user_id,))
        # Then delete the user
        db.execute('DELETE FROM users WHERE id = ? AND role = "patient"', (user_id,))
        db.commit()
        flash('Patient deleted successfully', 'success')
    except sqlite3.Error as e:
        flash(f'Error deleting patient: {str(e)}', 'danger')

    return redirect(url_for('admin_manage_users'))


@app.route('/admin/generate_report')
def admin_generate_report():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    db = get_db()

    # Get overall statistics
    total_patients = db.execute('SELECT COUNT(*) FROM users WHERE role = "patient"').fetchone()[0]
    total_scans = db.execute('SELECT COUNT(*) FROM scans').fetchone()[0]

    # Get diagnosis distribution
    diagnosis_stats = db.execute('''
        SELECT prediction, COUNT(*) as count
        FROM scans
        GROUP BY prediction
        ORDER BY count DESC
    ''').fetchall()

    # Get recent scans with patient details
    recent_scans = db.execute('''
        SELECT s.*, u.username, u.email
        FROM scans s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.created_at DESC
        LIMIT 10
    ''').fetchall()

    return render_template('admin_report.html',
                           total_patients=total_patients,
                           total_scans=total_scans,
                           diagnosis_stats=diagnosis_stats,
                           recent_scans=recent_scans)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
