# Phase 1 Impact: What’s Connected (Current State)

## Short answer

**Phase 1 is wired in.** The app uses **db_manager.py** and **musea.db** for users (with pseudo), museums, interactions, theme affinity, and discovery. The dashboard and tracking are backed by real DB data.

---

## Current architecture

| What | Source |
|------|--------|
| **Users / login** | **musea.db** `users` via `db_manager` (pseudo, theme_pref, etc.). Login uses `get_user_by_pseudo`; profile uses `get_user_profile`. |
| **Onboarding** | Writes to **users.db** (`user_profile`, `preferences`) and **musea.db** `users` via `db_manager.save_user_profile`. Source of truth for session is musea (user_id = pseudo). |
| **Museums** | **musea.db** `museums` via `db_manager.get_all_museums`, `get_museum_by_id`, `get_museums_by_theme`, `get_museums_for_discovery`. |
| **Interactions** | **musea.db** `interactions` via `db_manager.log_interaction`. Theme for scoring comes from `db_manager.get_museum_by_id(…).theme`. |
| **Theme affinity** | Computed from DB: `db_manager.get_theme_affinity_from_interactions(user_id)` (joins interactions + museums). Dashboard uses this, not in-memory mock. |
| **Engagement** | `db_manager.get_engagement_for_user(user_id)` from `interactions`. |
| **“Most Popular Museums”** | From **musea.db** `museums` by `popularity_score` via `db_manager.get_all_museums()` sorted; no mock. |
| **Scoring** | `scoring.process_interaction(…, theme=museum_theme)` still used for optional in-session updates; theme is passed from DB. |

---

## Legacy / deprecated

- **db_utils.py**: Legacy; app and tests use **db_manager.py**. Deprecated, kept only for reference.
- **users.db**: Still written by onboarding and reset_profile; profile display and login use musea.db. Can be phased out later by moving onboarding entirely to musea.
- **scoring.mock_db**: No longer used for dashboard theme affinity, top themes, or “Most Popular Museums.” Only used inside `process_interaction` for in-memory side effects; dashboard reads from DB.
- **user_has_profile** (app.py): Removed; was unused.

---

## Files that matter now

- **db_manager.py** – All musea.db access (users, museums, interactions, theme affinity, discovery).
- **database_setup.py** – Creates musea.db from schema.sql and imports museums from CSV.
- **schema.sql** – Defines users (with pseudo), museums, interactions.
- **test_db_phase1.py** – Uses db_manager; no longer uses db_utils.
