# 📚 Smart Book Finder

An intelligent book management system with AI/OCR book identification, Open Library lookup, fuzzy search, and role-based access control.

## Features

**Admin**
- Upload book images: automatic title/author extraction (Gemini AI or EasyOCR/Tesseract) with editable review form
- Edit extracted data before saving to database (can fix OCR errors)
- Add books manually without uploading images
- Edit book details: change quantity and shelf location
- Book identification via Open Library (canonical title/author, ISBN)
- Manage inventory and view all books
- View all books, list users, reset database

**Customer**
- Search books by title or author (partial + fuzzy/typo-tolerant)
- “Did you mean?” when search corrects typos
- No login required

**Technical**
- JWT auth, PBKDF2 password hashing, RBAC
- SQLite with indexes for fast search with many books
- Optional ISBN storage for identification

## Security

- **DO NOT commit `.env`** - It's in `.gitignore` for a reason. Contains API keys.
- Always use `.env.example` as a template and create `.env` locally with your own keys.
- Change the default admin password in production.
- Use environment variables for sensitive data (API keys, JWT secret).

## Project Structure

```
Smart Book Finder/
├── BACKEND/
│   ├── main.py           # FastAPI app & endpoints
│   ├── auth.py           # Auth & users
│   ├── ocr.py            # OCR (EasyOCR, Tesseract) + Gemini extraction
│   ├── book_lookup.py    # Open Library API identification
│   ├── database.py       # SQLite + fuzzy search
│   ├── requirements.txt # Python dependencies
│   ├── .env.example      # Env template
│   └── uploads/          # Uploaded images
├── Frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── README.md
├── SETUP.md
└── START_APP.bat
```

## Quick Start

### 1. Install dependencies

```powershell
cd BACKEND
pip install -r requirements.txt
```

Or: `pip install fastapi uvicorn pillow pytesseract easyocr requests opencv-python numpy pyjwt python-dotenv`

### 2. Optional: Gemini API (better recognition)

1. Get a key: https://aistudio.google.com/apikey  
2. Copy `BACKEND/.env.example` to `BACKEND/.env`  
3. Set `GEMINI_API_KEY=your_key`

### 3. Start backend

```powershell
cd BACKEND
uvicorn main:app --reload
```

Wait for: `✅ EasyOCR ready! Backend is fully initialized.`

### 4. Start frontend

```powershell
cd Frontend
python -m http.server 5500
```

### 5. Open app

http://localhost:5500  

**Login:** Admin `admin` / `admin123` — or continue as Customer (no login).

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | — | Health check |
| GET | `/status/` | — | Backend status |
| GET | `/search-book/?query=...` | — | Search (partial + fuzzy) |
| POST | `/auth/login/` | — | Login |
| POST | `/auth/register/` | — | Register |
| GET | `/auth/me/` | Bearer | Current user |
| POST | `/upload-book/` | Admin | Upload & extract from image |
| POST | `/save-extracted-book/` | Admin | Save extracted book (after review) |
| POST | `/add-book-manual/` | Admin | Add book manually |
| GET | `/books-for-edit/` | Admin | Get books with IDs |
| PUT | `/update-book/` | Admin | Update book (qty/shelf) |
| GET | `/debug/all-books/` | Admin | List all books |
| POST | `/debug/reset-database/` | Admin | Reset DB |
| GET | `/debug/list-users/` | Admin | List users |

## Database

**books:** id, title, author, quantity, shelf, isbn (indexed for search)  
**users:** id, username, password_hash, role, created_at, last_login, is_active  

## Tech Stack

- **Backend:** FastAPI, Uvicorn, SQLite3  
- **Frontend:** HTML5, CSS3, JavaScript  
- **OCR:** EasyOCR (default), Tesseract, optional Gemini  
- **Identification:** Open Library API (free, no key)  
- **Search:** LIKE + difflib fuzzy matching  
- **Auth:** PyJWT, PBKDF2-SHA256  

## Troubleshooting

- **Port in use:** Backend `--port 8001`, frontend `5501`; set `API_URL` in `Frontend/script.js` if needed.  
- **Login/UI issues:** Hard refresh (Ctrl+Shift+R), confirm backend at http://127.0.0.1:8000/  
- **OCR slow first run:** EasyOCR downloads ~100MB once; wait for “EasyOCR ready”.  
- **Change JWT secret:** Set `SECRET_KEY` in `BACKEND/.env`.  

## License

MIT.
