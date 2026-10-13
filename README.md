# Salon Management App

A simple Flask-based salon booking system.

## Features
- User registration & login
- Book, view, and cancel appointments
- Admin dashboard to manage services, staff, and appointments
- SQLite database (auto-created)

## Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize the database (seeds admin + sample data)
export FLASK_APP=salon.py     # Windows: set FLASK_APP=salon.py
flask init-db

# 4. Run the app
python salon.py
```

Open http://127.0.0.1:5000

**Default admin:** `admin` / `admin123`

## Routes
| Route | Description |
|-------|-------------|
| `/` | Home + service list |
| `/register` | Register new user |
| `/login` | Login |
| `/book` | Book appointment |
| `/appointments` | View appointments |
| `/admin` | Admin dashboard |
