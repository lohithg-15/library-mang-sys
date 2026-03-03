"""
Authentication module for Smart Book Finder
Handles user registration, login, JWT tokens, and role-based access control
"""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import jwt

# Use absolute path for database
DB_PATH = os.path.join(os.path.dirname(__file__), "books.db")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# User roles
ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"


def get_auth_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def create_users_table():
    """Create users table for authentication"""
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        """)
        conn.commit()
        
        # Create default admin account (username: admin, password: admin123)
        default_user = register_user("admin", "admin123", ROLE_ADMIN, force=True)
        if default_user:
            print("✅ Default admin account created (username: admin, password: admin123)")
        
        conn.close()
        print("✅ Users table initialized")
        return True
    except Exception as e:
        print(f"⚠️ Users table already exists or error: {e}")
        return False


def hash_password(password: str) -> str:
    """Hash password using SHA-256 + salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    try:
        salt, pwd_hash = password_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return new_hash.hex() == pwd_hash
    except Exception:
        return False


def register_user(username: str, password: str, role: str = ROLE_CUSTOMER, force: bool = False) -> Optional[Dict]:
    """Register a new user"""
    try:
        # Validate input
        if not username or len(username) < 3:
            return {"error": "Username must be at least 3 characters"}
        if not password or len(password) < 6:
            return {"error": "Password must be at least 6 characters"}
        if role not in [ROLE_ADMIN, ROLE_CUSTOMER]:
            return {"error": "Invalid role"}
        
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() and not force:
            conn.close()
            return {"error": "Username already exists"}
        
        # Hash password and insert
        password_hash = hash_password(password)
        cursor.execute("""
        INSERT OR REPLACE INTO users (username, password_hash, role, created_at)
        VALUES (?, ?, ?, ?)
        """, (username, password_hash, role, datetime.utcnow()))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"User '{username}' registered successfully",
            "username": username,
            "role": role
        }
    except Exception as e:
        return {"error": str(e)}


def login_user(username: str, password: str) -> Optional[Dict]:
    """Login user and return JWT token"""
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        
        # Get user from database
        cursor.execute("""
        SELECT id, username, password_hash, role, is_active 
        FROM users WHERE username = ?
        """, (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return {"error": "Invalid username or password", "success": False}
        
        if not user["is_active"]:
            return {"error": "User account is inactive", "success": False}
        
        # Verify password
        if not verify_password(password, user["password_hash"]):
            return {"error": "Invalid username or password", "success": False}
        
        # Generate JWT token
        payload = {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        # Update last login
        conn = get_auth_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                      (datetime.utcnow(), user["id"]))
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"]
            }
        }
    except Exception as e:
        return {"error": f"Login failed: {str(e)}", "success": False}


def verify_token(token: str) -> Optional[Dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user details by ID"""
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, created_at, last_login FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception:
        return None


def list_all_users() -> list:
    """List all registered users (admin only)"""
    try:
        conn = get_auth_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, created_at, last_login FROM users")
        users = cursor.fetchall()
        conn.close()
        return [dict(u) for u in users]
    except Exception:
        return []
