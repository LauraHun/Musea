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

## File Structure:
```
Adaptive System/
├── app.py              # Flask application
├── static/
│   └── style.css      # CSS file (served by Flask)
├── templates/
│   └── onboarding.html # HTML template (processed by Flask)
└── users.db           # Database (created automatically)
```
