# Musea – Adaptive Museum Explorer

Musea is a Flask-based adaptive recommender for French museums.  
It combines a **pseudo-based login**, an onboarding quiz, **explicit feedback** (thumbs up/down), and a **context-aware discovery page** that adapts to:

- User preferences (themes, distance, discovery style)
- Live interaction data (clicks, favorites, reading time)
- Context (device, connection quality, time available)

All persistent data lives in `musea.db` (SQLite).

---

## 1. How to Run / Comment exécuter

1. **Install dependencies**:

```bash
pip install -r requirements.txt
```

2. **Create / refresh `musea.db`** from the schema (and optionally import the CSV):

```bash
python database_setup.py --db musea.db
# or, with CSV import:
python database_setup.py --db musea.db --csv "musees-de-france-base-museofile (1).csv"
```

3. **Start the Flask app**:

```bash
python app.py
```

4. **Open the app** in your browser:

- Onboarding / sign-up: `http://localhost:5000/onboarding`  
- Login (pseudo): `http://localhost:5000/login`  
- Discovery gallery (home): `http://localhost:5000/`

> Note / Remarque: Opening the HTML files directly in the browser will not work; they rely on Flask (`{{ url_for(...) }}`) to load CSS and scripts.

---

## 2. Database Schema (musea.db)

Defined in `schema.sql` and used by `db_manager.py`:

- **`users`**
  - `user_id` (TEXT, PK) – same as pseudo for real users
  - `pseudo` (TEXT, UNIQUE, NOT NULL) – login identifier
  - `ui_language` (TEXT) – `English` / `French`
  - `visitor_type` (TEXT) – `Student`, `Tourist`, `Family`, `Curious`, etc.
  - `distance_pref` (TEXT) – `nearby`, `medium`, `far_ok`
  - `interest_mode` (TEXT) – `classics`, `balanced`, `hidden_gems`
  - `theme_pref` (TEXT) – comma-separated list of preferred themes
  - `created_at` (TIMESTAMP)

- **`museums`**
  - `id` (INTEGER, PK AUTOINCREMENT)
  - `identifiant` (TEXT, UNIQUE) – Museofile identifier
  - `name`, `region`, `theme`
  - `latitude`, `longitude`
  - `popularity_score` (INTEGER) – aggregate popularity
  - `location` (TEXT) – display location (e.g. "Lyon, Auvergne-Rhône-Alpes")
  - `description` (TEXT)
  - `website` (TEXT)
  - `image_url` (TEXT)
  - `thumbs_up` / `thumbs_down` (INTEGER DEFAULT 0) – explicit feedback
  - `created_at` (TIMESTAMP)

- **`interactions`**
  - `id` (INTEGER, PK AUTOINCREMENT)
  - `user_id` (TEXT, FK → users.user_id)
  - `museum_id` (INTEGER, FK → museums.id)
  - `click_type` (TEXT) – `click`, `view-details`, `reading`, `favorite`, `thumbs_up`, `thumbs_down`, `website_visit`
  - `duration_sec` (REAL, default 0)
  - `created_at` (TIMESTAMP)

Indexes are created for `museums.theme`, `museums.region`, `interactions.user_id`, `interactions.museum_id`, and (`user_id`, `museum_id`, `click_type`) for fast feedback lookups.

---

## 3. High-Level Architecture

- **`app.py`** – Flask application:
  - Onboarding (`/onboarding`, `/submit_onboarding`)
  - Login / logout (`/login`, `/logout`)
  - Discovery gallery (`/museum_gallery`)
  - Museum details (`/museum/<id>`)
  - Dashboard (`/user_profile`)
  - Favorites / history (`/favorites`, `/history`)
  - Feedback API (`/feedback`) and interaction tracking API (`/track_interaction`)

- **`db_manager.py`** – All SQL and data logic for `musea.db`:
  - Users: `save_user_profile`, `get_user_profile`, `get_user_by_pseudo`
  - Interactions: `log_interaction`, `get_engagement_for_user`, `get_theme_affinity_from_interactions`
  - Museums: `get_all_museums`, `get_museum_by_id`, `get_museums_for_discovery_all`, `get_hidden_gems`, `get_similar_museums`
  - Distance-aware filtering: `_annotate_and_filter_by_distance` using lat/long + hub city

- **`adaptation.py`** – Context-aware adaptation engine:
  - Detects `device` (desktop / mobile / tablet), `connection_quality`, `time_available`
  - Derives `max_results`, `layout`, `description_length`, `show_images`
  - Produces a human-readable adaptation log for transparency.

- **`scoring.py`** – Stateless scoring utilities:
  - `calculate_interaction_points` (click, reading, favorite, thumbs, etc.)
  - `process_interaction` returns a structured summary of points for an interaction
  - All persistence of scores is handled by `db_manager` (no more in-memory mock DB).

- **Frontend**:
  - Templates (`templates/*.html`) for onboarding, gallery, detail view, dashboard, favorites/history.
  - Static assets:
    - `static/style.css` – responsive Musea theme
    - `static/js/dark-mode.js` – dark mode + mobile navigation
    - `static/js/tracking.js` – interaction tracking (clicks, favorites, reading time, explicit feedback).

---

## 4. Personalisation & Adaptation

### Onboarding (Profil utilisateur)

The onboarding quiz collects:

- Interface language / Langue (`ui_language`)
- Visitor type / Type de visiteur (`visitor_type`)
- Preferred themes / Thèmes préférés (`theme_pref`)
- Distance preference / Préférence de distance (`distance_pref` = nearby / medium / far_ok)
- Discovery style / Style de découverte (`interest_mode` = classics / balanced / hidden_gems)
- Hub city / Ville de référence (`hub_city`) – used for distance in km

Data is written into `musea.db.users` via `db_manager.save_user_profile`.

### Adaptation rules (in `adaptation.py`)

- **Bandwidth rule**: if `connection_quality == 'poor'` → hide images.
- **Time constraint rule**: if `time_available <= 15` minutes → show only a few results and shorten descriptions.
- **Mobile rule**: if `device == 'mobile'` → use list layout instead of grid.

The discovery route (`/museum_gallery`) calls `detect_context(request)` and `get_active_settings(...)`, then passes the resulting `settings` to `museum_gallery.html` and surfaces a short adaptation log (“Why am I seeing this?”).

### Distance-aware discovery

Using `hub_city` and museum coordinates (`latitude`, `longitude`), `db_manager._annotate_and_filter_by_distance` computes `distance_km` and filters based on:

- `nearby` → museums `< 20 km`
- `medium` → museums `<= 50 km` (includes nearby)
- `far_ok` / `far` → all museums with a known distance (near + medium + far)

Distances are displayed on cards (e.g. “42 km away”) on both the gallery and detail pages.

### Discovery style (classics / balanced / hidden_gems)

`db_manager.get_museums_for_discovery` and `get_museums_for_discovery_all`:

- Adjust the **exploration ratio** (percentage of out-of-preference themes) based on `interest_mode` and engagement.
- Promote the top dynamic themes (from interactions) into the preferred set, so the system adapts over time to what the user actually clicks on.

---

## 5. Tracking & Scoring

### Frontend tracking (`static/js/tracking.js`)

Tracks:

- Card clicks and “View Details” clicks (`interaction_type = 'click'`)
- Favorites (heart icon), synced to `localStorage` and `/track_interaction`
- Reading time on the detail page (with pause/resume on tab visibility)
- Explicit thumbs up/down buttons, calling `/feedback`

All tracking POSTs go to:

- `/track_interaction` – for general interactions (non-blocking, best-effort)
- `/feedback` – for thumbs up/down (single vote per user/museum)

Errors are handled gracefully (console warnings; UI never breaks).

### Backend scoring (`scoring.py` + `db_manager.py`)

- `calculate_interaction_points` maps each interaction to a number of points:
  - Click: +1, Detail open: +2, Favorite: +3
  - Reading time: +1 per 30 seconds (capped)
  - Thumbs up/down: positive/low weight
- `process_interaction` is called from `/track_interaction` and `/feedback` as a **best-effort** side-effect: if scoring fails, the HTTP response still succeeds.
- Theme affinities, engagement scores, and popularity scores used by the dashboard come from real DB queries in `db_manager` (`get_theme_affinity_from_interactions`, `get_engagement_for_user`, `get_all_museums`).

---

## 6. Key Routes (Résumé des routes)

- `/` → redirect to `/museum_gallery`
- `/onboarding` – onboarding quiz (no login required)
- `/submit_onboarding` – saves onboarding profile to `musea.db`
- `/login` / `/logout` – pseudo-based login / logout
- `/museum_gallery` – main discovery page (For You / Hidden Gems tabs, theme filter, distance filter, time-aware result count)
- `/museum/<id>` – detail page (with “You may also like” recommendations)
- `/user_profile` – dashboard (engagement analytics, theme affinities, explainability section)
- `/favorites`, `/history` – lists based on `localStorage` (login required to access)
- `/profile/edit` – edits `theme_pref`, `distance_pref`, `interest_mode`
- `/track_interaction` (POST) – interaction tracking API
- `/feedback` (POST) – explicit thumbs up/down with single-vote guarantee

---

## 7. Project Structure (Répertoire)

```
Adaptive System/
├── app.py               # Flask app: routes, session, wiring to db_manager/adaptation
├── db_manager.py        # All SQL/data logic for musea.db
├── adaptation.py        # Adaptation engine (rules + context detection)
├── scoring.py           # Stateless scoring helpers (points per interaction)
├── schema.sql           # Final DB schema (users, museums, interactions, indexes)
├── database_setup.py    # CLI: create musea.db and import museums CSV
├── test_db_phase1.py    # DB smoke tests (schema + db_manager)
├── generate_fake_data.py # Optional: seed ghost users and biased feedback
├── static/
│   ├── style.css
│   └── js/
│       ├── tracking.js
│       └── dark-mode.js
└── templates/
    ├── onboarding.html
    ├── login.html
    ├── museum_gallery.html
    ├── museum_detail.html
    ├── user_profile.html
    ├── favorites.html
    ├── history.html
    └── profile_edit.html
```

This single README now replaces previous HOW_TO_RUN / engine-specific docs; all up‑to‑date information is centralized here.
