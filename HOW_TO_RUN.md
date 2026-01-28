# How to Run the Application

## Important: You MUST run Flask to see the styles!

The HTML templates use Flask syntax (`{{ url_for(...) }}`) which only works when Flask is running. Opening the HTML file directly in a browser will NOT work.

## Steps to Run:

1. **Install Flask** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Flask application**:
   ```bash
   python app.py
   ```

3. **Open your browser** and go to:
   ```
   http://localhost:5000/onboarding
   ```

4. The styles should now load correctly!

## Troubleshooting:

- If you see "Python is not found": Make sure Python is installed and in your PATH
- If styles still don't load: Check that the `static/style.css` file exists
- If you get a 404 error: Make sure you're accessing the URL through Flask (localhost:5000), not opening the file directly

## Testing Phase 1 (Database & db_manager)

To verify `schema.sql`, `database_setup.py`, and `db_manager.py`:

1. **Create DB and load museums from CSV** (from project root):
   ```bash
   python database_setup.py --db musea.db --csv "musees-de-france-base-museofile (1).csv"
   ```
   Or only create an empty DB:
   ```bash
   python database_setup.py --db musea.db
   ```

2. **Run the Phase 1 test script**:
   ```bash
   python test_db_phase1.py
   ```
   This checks: DB init, CSV import (if the file exists), `db_manager.save_user_profile` (with pseudo), `db_manager.get_museums_by_theme`, and `db_manager.log_interaction`.

3. **Quick Python check** (optional):
   ```python
   import db_manager
   db_manager.save_user_profile({"user_id": "x", "pseudo": "x", "ui_language": "en", "visitor_type": "Tourist", "distance_pref": "medium", "interest_mode": "balanced", "theme_pref": "Art"})
   print(db_manager.get_museums_by_theme("Art"))  # list of dicts
   db_manager.log_interaction("x", 1, "view-details", 10.0)
   ```

   **Note:** `db_utils.py` is legacy/deprecated; the app and tests use `db_manager.py` (musea.db).

## Pseudo-based login and musea.db

The app uses **musea.db** for users (with a unique `pseudo` column), museums, and interactions. Login and registration are pseudo-based: users pick a pseudo in onboarding and log in later with that pseudo.

- **New install**: Create musea.db from the current `schema.sql` (e.g. run `database_setup.py` or your init script). The schema includes `users.pseudo TEXT UNIQUE NOT NULL`.
- **“no such column: pseudo” when signing up**: Your musea.db was created before the pseudo column existed. Stop the Flask app, then run:
  ```bash
  python migrate_add_pseudo.py
  ```
  That adds the `pseudo` column and backfills it. Then start the app again and try signing up.

## File Structure:
```
Adaptive System/
├── app.py              # Flask application
├── database_setup.py   # Phase 1: init DB, import museums CSV
├── db_manager.py       # musea.db: users (pseudo), museums, interactions
├── db_utils.py         # Legacy (deprecated); app uses db_manager
├── schema.sql          # Phase 1: users (with pseudo), museums, interactions
├── test_db_phase1.py   # Phase 1 test script
├── static/
│   └── style.css      # CSS file (served by Flask)
├── templates/
│   ├── onboarding.html # Sign-up (includes "Pick a Pseudo")
│   └── login.html      # Pseudo-only login
├── users.db           # Legacy/onboarding DB (created by app)
└── musea.db           # Phase 1 DB (users, museums, interactions)
```
