# Adaptive Museum Explorer - Onboarding System

## Overview
This Flask application implements Step 2: Enriched User Profile with a mandatory onboarding quiz that captures static user attributes for personalized museum recommendations in France.

## Features
- **Mandatory Onboarding Quiz**: Captures user preferences on first visit
- **Database Integration**: SQLite database with `user_profile` and `preferences` tables
- **Access Control**: Automatic redirect to onboarding if user profile is incomplete
- **Responsive Design**: Mobile-friendly interface with Heritage & Culture theme
- **Bilingual Support**: French/English interface

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. The database (`users.db`) will be automatically created on first run.

## Database Schema

### `user_profile` table
- `user_id` (TEXT, PRIMARY KEY)
- `ui_language` (TEXT) - "English" or "French"
- `visitor_type` (TEXT) - "Student", "Tourist", "Family", or "Curious"
- `distance_pref` (TEXT) - "nearby", "medium", or "far_ok"
- `interest_mode` (TEXT) - "classics", "balanced", or "hidden_gems"

### `preferences` table
- `id` (INTEGER, PRIMARY KEY, AUTOINCREMENT)
- `user_id` (TEXT, FOREIGN KEY)
- `preferred_themes` (TEXT) - "Art", "History", "Science", or "Local Heritage"

## Routes

- `/` - Main index page (redirects to onboarding if profile incomplete)
- `/onboarding` - Onboarding quiz form
- `/submit_onboarding` - POST endpoint for form submission

## Access Control

The application uses `@app.before_request` to check if a logged-in user has completed onboarding. Users without a profile are automatically redirected to `/onboarding`.

**Note**: Currently uses session-based demo user authentication. In production, integrate with your actual authentication system.

## Form Fields

1. **Language** (Dropdown): English or French
2. **Visitor Type** (Dropdown): Student, Tourist, Family, or Curious
3. **Preferred Themes** (Multi-select checkboxes): Art, History, Science, Local Heritage
4. **Distance Preference** (Radio buttons): Nearby, Medium, or Far is OK
5. **Interest Mode** (Radio buttons): Classics, Balanced, or Hidden Gems

## Project Structure

```
.
├── app.py                 # Flask application and routes
├── requirements.txt       # Python dependencies
├── users.db              # SQLite database (created automatically)
├── templates/
│   ├── onboarding.html   # Onboarding quiz form
│   └── index.html        # Main page after onboarding
└── static/
    └── style.css         # Responsive CSS styling
```
