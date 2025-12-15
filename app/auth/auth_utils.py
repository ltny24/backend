"""
Authentication utilities for user management
Handles password hashing, token generation, and CSV-based user storage
"""
import csv
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json

# File path cho CSV database
USERS_CSV_FILE = "users.csv"
SESSIONS_FILE = "sessions.json"

# ---- PASSWORD HASHING ----
def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        salt, pwd_hash = hashed_password.split('$')
        return hashlib.sha256((plain_password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False

# ---- TOKEN GENERATION ----
def generate_token() -> str:
    """Generate a random access token"""
    return secrets.token_urlsafe(32)

# ---- USER CSV OPERATIONS ----
def init_csv_file():
    """Initialize CSV file if it doesn't exist"""
    if not os.path.exists(USERS_CSV_FILE):
        with open(USERS_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'email', 'password_hash', 'first_name', 'last_name', 'phone_number', 'created_at'])

def get_next_user_id() -> int:
    """Get the next available user ID"""
    init_csv_file()
    try:
        with open(USERS_CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            users = list(reader)
            if users:
                return max(int(user['user_id']) for user in users) + 1
            return 1
    except:
        return 1

def find_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Find a user by email address"""
    init_csv_file()
    try:
        with open(USERS_CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['email'].lower() == email.lower():
                    return row
    except:
        pass
    return None

def create_user(email: str, password: str, first_name: str, last_name: str, phone_number: str = "") -> Dict[str, Any]:
    """Create a new user and save to CSV"""
    init_csv_file()
    
    # Check if user already exists
    if find_user_by_email(email):
        raise ValueError("Email already registered")
    
    # Create user data
    user_id = get_next_user_id()
    password_hash = hash_password(password) if password else ""
    created_at = datetime.now().isoformat()
    
    # Append to CSV
    with open(USERS_CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, email, password_hash, first_name, last_name, phone_number, created_at])
    
    return {
        'user_id': user_id,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'phone_number': phone_number,
        'created_at': created_at
    }

def create_or_get_oauth_user(email: str, first_name: str, last_name: str, oauth_provider: str) -> Dict[str, Any]:
    """Create or get existing user from OAuth login"""
    init_csv_file()
    
    # Check if user exists
    existing_user = find_user_by_email(email)
    if existing_user:
        return {
            'user_id': existing_user['user_id'],
            'email': existing_user['email'],
            'first_name': existing_user['first_name'],
            'last_name': existing_user['last_name'],
            'phone_number': existing_user['phone_number'],
            'created_at': existing_user['created_at']
        }
    
    # Create new user without password (OAuth user)
    return create_user(
        email=email,
        password="",  # No password for OAuth users
        first_name=first_name,
        last_name=last_name,
        phone_number=""
    )

def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with email and password"""
    user = find_user_by_email(email)
    if not user:
        return None
    
    if not verify_password(password, user['password_hash']):
        return None
    
    # Return user data without password hash
    return {
        'user_id': user['user_id'],
        'email': user['email'],
        'first_name': user['first_name'],
        'last_name': user['last_name'],
        'phone_number': user['phone_number'],
        'created_at': user['created_at']
    }

# ---- SESSION MANAGEMENT ----
def save_session(token: str, user_data: Dict[str, Any], expires_hours: int = 24):
    """Save user session with token"""
    sessions = load_sessions()
    sessions[token] = {
        'user': user_data,
        'expires_at': (datetime.now() + timedelta(hours=expires_hours)).isoformat()
    }
    
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2)

def load_sessions() -> Dict[str, Any]:
    """Load all sessions from file"""
    if not os.path.exists(SESSIONS_FILE):
        return {}
    
    try:
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Get user data from access token"""
    sessions = load_sessions()
    session = sessions.get(token)
    
    if not session:
        return None
    
    # Check if token expired
    expires_at = datetime.fromisoformat(session['expires_at'])
    if datetime.now() > expires_at:
        return None
    
    return session['user']

def delete_session(token: str):
    """Delete a session (logout)"""
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=2)
