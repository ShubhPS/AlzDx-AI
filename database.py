import sqlite3
import os
from datetime import datetime
import hashlib
import json
import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

class Database:
    def __init__(self):
        self.db_path = 'alzheimer.db'
        self.init_db()

    def init_db(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create users table with oauth fields
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                oauth_provider TEXT,
                oauth_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(oauth_provider, oauth_id)
            )
        ''')

        # Create patient_details table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patient_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                date_of_birth DATE NOT NULL,
                gender TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                emergency_contact TEXT,
                medical_history TEXT,
                profile_image TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create scan_results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scan_image_path TEXT NOT NULL,
                predicted_class TEXT NOT NULL,
                confidence REAL NOT NULL,
                probabilities TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES users (id)
            )
        ''')

        # Create activity_log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create system_settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

        # Create admin user if not exists
        self.create_admin_user()

    def create_admin_user(self):
        """Create default admin user if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if admin exists
        cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            # Create admin user
            hashed_password = self.hash_password('admin123')
            cursor.execute('''
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            ''', ('admin', hashed_password, 'admin@neuroscan.ai', 'admin'))
            conn.commit()

        conn.close()

    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate_user(self, username, password, role):
        """Authenticate user and return user data if successful"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        hashed_password = self.hash_password(password)
        cursor.execute('''
            SELECT id, username, email, role
            FROM users
            WHERE username = ? AND password = ? AND role = ?
        ''', (username, hashed_password, role))

        user = cursor.fetchone()
        conn.close()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3]
            }
        return None

    def add_user(self, username, password, email, role):
        """Add new user to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            hashed_password = self.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            ''', (username, hashed_password, email, role))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user_by_username(self, username):
        """Get user data by username"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, username, email, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3]
            }
        return None

    def add_patient_details(self, user_id, full_name, date_of_birth, gender,
                          address, phone, emergency_contact, medical_history):
        """Add patient details to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO patient_details (
                user_id, full_name, date_of_birth, gender,
                address, phone, emergency_contact, medical_history
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, full_name, date_of_birth, gender,
              address, phone, emergency_contact, medical_history))
        
        conn.commit()
        conn.close()

    def get_patient_details(self, user_id):
        """Get patient details by user ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT full_name, date_of_birth, gender, address,
                   phone, emergency_contact, medical_history
            FROM patient_details
            WHERE user_id = ?
        ''', (user_id,))
        
        details = cursor.fetchone()
        conn.close()

        if details:
            return {
                'full_name': details[0],
                'date_of_birth': details[1],
                'gender': details[2],
                'address': details[3],
                'phone': details[4],
                'emergency_contact': details[5],
                'medical_history': details[6]
            }
        return None

    def save_scan_result(self, patient_id, scan_image_path, predicted_class,
                        confidence, probabilities):
        """Save scan result to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO scan_results (
                patient_id, scan_image_path, predicted_class,
                confidence, probabilities
            )
            VALUES (?, ?, ?, ?, ?)
        ''', (patient_id, scan_image_path, predicted_class,
              confidence, json.dumps(probabilities)))
        
        scan_id = cursor.lastrowid

        # Log activity
        cursor.execute('''
            INSERT INTO activity_log (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (patient_id, 'New Scan', f'Scan ID: {scan_id}, Class: {predicted_class}'))

        conn.commit()
        conn.close()
        return scan_id

    def get_latest_scan(self, patient_id):
        """Get the most recent scan result for a patient"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, scan_date, predicted_class, confidence, probabilities
            FROM scan_results
            WHERE patient_id = ?
            ORDER BY scan_date DESC
            LIMIT 1
        ''', (patient_id,))
        
        scan = cursor.fetchone()
        conn.close()

        if scan:
            return {
                'id': scan[0],
                'scan_date': scan[1],
                'predicted_class': scan[2],
                'confidence': scan[3],
                'probabilities': json.loads(scan[4])
            }
        return None

    def get_scan_history(self, patient_id):
        """Get scan history for a patient"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, scan_date, predicted_class, confidence, probabilities
            FROM scan_results
            WHERE patient_id = ?
            ORDER BY scan_date DESC
        ''', (patient_id,))
        
        scans = cursor.fetchall()
        conn.close()

        return [{
            'id': scan[0],
            'scan_date': scan[1],
            'predicted_class': scan[2],
            'confidence': scan[3],
            'probabilities': json.loads(scan[4])
        } for scan in scans]

    def get_total_patients(self):
        """Get total number of patients"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('patient',))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_total_scans(self):
        """Get total number of scans"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM scan_results')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_active_patients(self):
        """Get number of active patients (with scans in last 30 days)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(DISTINCT patient_id)
            FROM scan_results
            WHERE scan_date >= datetime('now', '-30 days')
        ''')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_recent_activity(self, limit=10):
        """Get recent activity log entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT al.timestamp, al.action, u.username, al.details
            FROM activity_log al
            JOIN users u ON al.user_id = u.id
            ORDER BY al.timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        activities = cursor.fetchall()
        conn.close()

        return [{
            'time': activity[0],
            'action': activity[1],
            'user': activity[2],
            'details': activity[3]
        } for activity in activities]

    def get_last_backup(self):
        """Get last backup timestamp"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = 'last_backup'
        ''')
        
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 'Never'

    def get_next_checkup(self, patient_id):
        """Get next checkup date for a patient"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = ?
        ''', (f'next_checkup_{patient_id}',))
        
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 'Not scheduled'

    def get_doctor_notes(self, patient_id):
        """Get doctor's notes for a patient"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT setting_value
            FROM system_settings
            WHERE setting_key = ?
        ''', (f'doctor_notes_{patient_id}',))
        
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 'No notes available'

    def get_user_by_email(self, email):
        """Get user data by email"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, username, email, role FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3]
            }
        return None

    def get_user_by_oauth(self, provider, oauth_id):
        """Get user data by OAuth provider and ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role 
            FROM users 
            WHERE oauth_provider = ? AND oauth_id = ?
        ''', (provider, oauth_id))
        
        user = cursor.fetchone()
        conn.close()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3]
            }
        return None

    def add_oauth_user(self, username, email, oauth_provider, oauth_id, role='patient'):
        """Add new user with OAuth credentials"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Generate a random password for OAuth users
            password = os.urandom(24).hex()
            hashed_password = self.hash_password(password)
            
            cursor.execute('''
                INSERT INTO users (
                    username, password, email, role, oauth_provider, oauth_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, hashed_password, email, role, oauth_provider, oauth_id))
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def update_user_profile(self, user_id, **kwargs):
        """Update user profile information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Build the update query dynamically based on provided fields
            fields = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = ?")
                    values.append(value)

            if fields:
                query = f'''
                    UPDATE patient_details 
                    SET {", ".join(fields)}
                    WHERE user_id = ?
                '''
                values.append(user_id)
                cursor.execute(query, values)
                conn.commit()
                return True
            return False
        finally:
            conn.close()

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    
    # Create tables
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            prediction TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create default admin user if not exists
    admin_exists = db.execute(
        'SELECT id FROM users WHERE username = ?',
        (current_app.config['ADMIN_USERNAME'],)
    ).fetchone()
    
    if not admin_exists:
        db.execute(
            'INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
            (
                current_app.config['ADMIN_USERNAME'],
                current_app.config['ADMIN_EMAIL'],
                generate_password_hash(current_app.config['ADMIN_PASSWORD']),
                True
            )
        )
    
    db.commit()

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

@click.command('init-db')
def init_db_command():
    """Clear existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

# Helper functions for common database operations
def get_user_by_username(username):
    return get_db().execute(
        'SELECT * FROM users WHERE username = ?',
        (username,)
    ).fetchone()

def get_user_by_email(email):
    return get_db().execute(
        'SELECT * FROM users WHERE email = ?',
        (email,)
    ).fetchone()

def get_user_scans(user_id):
    return get_db().execute(
        '''SELECT * FROM scans 
           WHERE user_id = ? 
           ORDER BY created_at DESC''',
        (user_id,)
    ).fetchall()

def get_recent_scans(limit=10):
    return get_db().execute(
        '''SELECT s.*, u.username 
           FROM scans s 
           JOIN users u ON s.user_id = u.id 
           ORDER BY s.created_at DESC 
           LIMIT ?''',
        (limit,)
    ).fetchall()

def get_stats():
    db = get_db()
    stats = {}
    
    # Get total patients (non-admin users)
    stats['total_patients'] = db.execute(
        'SELECT COUNT(*) as count FROM users WHERE is_admin = 0'
    ).fetchone()['count']
    
    # Get total scans
    stats['total_scans'] = db.execute(
        'SELECT COUNT(*) as count FROM scans'
    ).fetchone()['count']
    
    # Get scans by prediction
    stats['prediction_counts'] = db.execute(
        '''SELECT prediction, COUNT(*) as count 
           FROM scans 
           GROUP BY prediction'''
    ).fetchall()
    
    return stats 