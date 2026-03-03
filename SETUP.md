# ⚡ Quick Start

## 1. Install dependencies

```powershell
cd BACKEND
pip install -r requirements.txt
```

## 2. Optional: Gemini API (better book recognition)

1. Get a free key: https://aistudio.google.com/apikey  
2. In `BACKEND`, copy `.env.example` to `.env`  
3. Set: `GEMINI_API_KEY=your_actual_key`

## 3. Start backend (Terminal 1)

```powershell
cd BACKEND
uvicorn main:app --reload
```

Wait for: `✅ EasyOCR ready! Backend is fully initialized.`

## 4. Start frontend (Terminal 2)

```powershell
cd Frontend
python -m http.server 5500
```

## 5. Open app

http://localhost:5500  

**Login:** `admin` / `admin123` — or **Continue as Customer** (no login).

---

## What you can do

**Admin Workflows:**

1. **Upload & Review:**
   - Upload a book image
   - System extracts title/author using Gemini AI or OCR
   - Review extracted data in an editable form (yellow background)
   - Edit any field if OCR made mistakes
   - Click **"Save to Database"** to confirm
   - OR Click **"Cancel"** to discard

2. **Add Manually:**
   - Enter title, author, quantity, shelf location directly
   - Click **"Add Book"** to save immediately

3. **Manage & Edit:**
   - Click **"Manage Books"** tab
   - Click **"Load Books"** to see all books
   - Click **"Edit"** button on any book
   - Modify quantity/shelf/title/author
   - Click **"Save"** to update database

**Customer:** Search by title or author (typo-tolerant; "Did you mean?" when applicable). No login needed.

---

## Issues

- **Clicks do nothing:** Ensure backend is running at http://127.0.0.1:8000/ and refresh (Ctrl+Shift+R). Check browser console (F12).  
- **Backend won’t start:** Use Python 3.8+; install missing packages; stop other process (Ctrl+C).  
- **Port in use:** Run backend on another port, e.g. `uvicorn main:app --port 8001`, and set `API_URL` in `Frontend/script.js` to `http://127.0.0.1:8001`.
