# Adaptive Museum Explorer

## Overview
This Flask application implements an adaptive museum recommender with a mandatory onboarding quiz, pseudo-based login, and personalized discovery (80% interests, 20% exploration). Data lives in **musea.db** (users with pseudo, museums, interactions). Theme affinity and engagement are computed from interactions and museum themes.

## Features
- **Pseudo-based login**: Sign up via onboarding (pick a pseudo); log in with that pseudo
- **musea.db**: Users (pseudo, theme_pref, distance, etc.), museums (from CSV), interactions (clicks, reading, favorites)
- **Dashboard**: Engagement score and theme affinity from real interactions; “Most Popular Museums” from DB `popularity_score`
- **Adaptation**: Context-aware settings (connection, time, device) from `adaptation.py`
- **Bilingual**: French/English interface

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create musea.db (schema + optional CSV import):
```bash
python database_setup.py --db musea.db
# or with CSV: python database_setup.py --db musea.db --csv "musees-de-france-base-museofile (1).csv"
```

3. Run the application:
```bash
python app.py
```

4. `users.db` is still created by the app for legacy onboarding tables; **musea.db** is the source of truth for login, profiles, museums, and interactions.

## Database (musea.db)

- **users**: `user_id`, `pseudo` (unique, for login), `ui_language`, `visitor_type`, `distance_pref`, `interest_mode`, `theme_pref`
- **museums**: id, name, region, theme, popularity_score, etc. (from Museofile CSV)
- **interactions**: user_id, museum_id, click_type, duration_sec

## Routes

- `/` → redirects to museum gallery (Discovery)
- `/onboarding` – Sign-up quiz (pseudo, language, visitor type, themes, distance, interest mode)
- `/login`, `/logout` – Pseudo-based session
- `/museum_gallery` – Discovery (80% interests, 20% other; adapts with engagement)
- `/user_profile` – Dashboard (engagement, theme affinity, top themes, popular museums from DB)
- `/favorites`, `/history` – Require login; frontend filters by localStorage
- `/profile/edit` – Edit interests and distance only

## Access Control

Login-required routes use `@login_required` and redirect to `/login` when there is no `session['user_id']`. Tracking and dashboard use the logged-in user’s data from musea.db.

## Onboarding form fields

1. **Language** (Dropdown): English or French  
2. **Pseudo** (Text): Unique handle used to log in later  
3. **Visitor Type**: Student, Tourist, Family, or Curious  
4. **Preferred Themes**: Art, History, Science, Local Heritage  
5. **Distance Preference**: Nearby, Medium, or Far  
6. **Interest Mode**: Classics, Balanced, or Hidden Gems  

## Project Structure

```
.
├── app.py                 # Flask application and routes
├── db_manager.py          # musea.db: users, museums, interactions, theme affinity
├── adaptation.py          # Context-aware UI settings
├── scoring.py             # process_interaction (points, theme from DB when provided)
├── requirements.txt       # Python dependencies
├── musea.db               # Main DB: users (pseudo), museums, interactions
├── users.db               # Legacy: user_profile, preferences (still written by onboarding)
├── templates/
│   ├── onboarding.html  # Sign-up (pseudo, language, visitor type, themes, distance)
│   ├── login.html         # Pseudo-only login
│   ├── museum_gallery.html, museum_detail.html, user_profile.html, favorites.html, history.html, profile_edit.html
└── static/
    └── style.css          # Responsive CSS styling
```
