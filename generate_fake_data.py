"""
Musea: Fake Data Seeder
-----------------------

Standalone script to "prime" musea.db with:
- 5–10 ghost users (pseudo-based users with preferences)
- 50–100 random interactions (clicks, favorites, reading time)
- Explicit thumbs up / down feedback with a strategic bias:
  * "Louvre" = many interactions but only mediocre approval
  * "Musée Rodin" = few interactions but 100% thumbs up

Run it once from the project root:

    python generate_fake_data.py

It will connect to musea.db in the same directory as this script.
"""

from __future__ import annotations

import os
import random
import sqlite3
from typing import List, Tuple, Dict


DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")


GHOST_PSEUDOS = [
    "ArtLover99",
    "HistoryBuff",
    "TechExplorer",
    "QuietCurator",
    "WeekendWanderer",
    "ScienceGeek",
    "HiddenGemHunter",
    "FamilyTripPlanner",
]

UI_LANGUAGES = ["English", "French"]
VISITOR_TYPES = ["Student", "Tourist", "Local", "Family", "Researcher"]
DISTANCE_PREFS = ["short", "medium", "long"]
INTEREST_MODES = ["Exploration", "Goal-Oriented", "Relaxed"]
THEMES = ["Art", "History", "Science", "Local Heritage"]
HUB_CITY_CHOICES = ["Lyon", "Clermont-Ferrand", "Saint-Étienne", "Grenoble"]


def connect_db(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_feedback_columns(conn: sqlite3.Connection) -> None:
    """Make sure thumbs_up / thumbs_down and hub_city columns exist."""
    alters = [
        "ALTER TABLE museums ADD COLUMN thumbs_up INTEGER DEFAULT 0",
        "ALTER TABLE museums ADD COLUMN thumbs_down INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN hub_city TEXT",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists – safe to ignore
            pass


def create_ghost_users(conn: sqlite3.Connection) -> List[str]:
    """
    Create 5–10 ghost users with random preferences.
    Returns the list of user_ids created.
    """
    cur = conn.cursor()
    n_users = random.randint(5, min(10, len(GHOST_PSEUDOS)))
    chosen_pseudos = random.sample(GHOST_PSEUDOS, n_users)
    user_ids: List[str] = []

    for pseudo in chosen_pseudos:
        user_id = pseudo  # In this app, user_id == pseudo
        ui_language = random.choice(UI_LANGUAGES)
        visitor_type = random.choice(VISITOR_TYPES)
        distance_pref = random.choice(DISTANCE_PREFS)
        interest_mode = random.choice(INTEREST_MODES)
        # 1–3 themes as comma-separated preference
        k = random.randint(1, min(3, len(THEMES)))
        theme_pref = ",".join(random.sample(THEMES, k))
        hub_city = random.choice(HUB_CITY_CHOICES)

        cur.execute(
            """
            INSERT INTO users (user_id, pseudo, ui_language, visitor_type,
                               distance_pref, interest_mode, theme_pref, hub_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                pseudo = excluded.pseudo,
                ui_language = excluded.ui_language,
                visitor_type = excluded.visitor_type,
                distance_pref = excluded.distance_pref,
                interest_mode = excluded.interest_mode,
                theme_pref = excluded.theme_pref,
                hub_city = EXCLUDED.hub_city
            """,
            (
                user_id,
                pseudo,
                ui_language,
                visitor_type,
                distance_pref,
                interest_mode,
                theme_pref,
                hub_city,
            ),
        )
        user_ids.append(user_id)

    conn.commit()
    print(f"Created/updated {len(user_ids)} ghost users.")
    return user_ids


def get_museums(conn: sqlite3.Connection) -> Tuple[List[Dict], int | None, int | None]:
    """
    Return (all_museums, louvre_id, rodin_id).
    Louvre / Rodin ids are best-effort matches by name.
    """
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id, name FROM museums ORDER BY name"
    ).fetchall()
    museums = [dict(r) for r in rows]
    if not museums:
        raise RuntimeError("No museums found in musea.db – did you import the CSV?")

    def find_by_keyword(keyword: str) -> int | None:
        keyword_lower = keyword.lower()
        for m in museums:
            if keyword_lower in (m["name"] or "").lower():
                return int(m["id"])
        return None

    louvre_id = find_by_keyword("louvre")
    rodin_id = find_by_keyword("rodin")

    if louvre_id is None:
        print("WARNING: Could not find a museum containing 'Louvre' in its name.")
    else:
        print(f"Louvre candidate id={louvre_id}")
    if rodin_id is None:
        print("WARNING: Could not find a museum containing 'Rodin' in its name.")
    else:
        print(f"Musée Rodin candidate id={rodin_id}")

    return museums, louvre_id, rodin_id


def insert_interaction(
    cur: sqlite3.Cursor,
    user_id: str,
    museum_id: int,
    click_type: str,
    duration_sec: float = 0.0,
) -> None:
    cur.execute(
        """
        INSERT INTO interactions (user_id, museum_id, click_type, duration_sec)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, int(museum_id), click_type, float(duration_sec)),
    )


def seed_random_interactions(
    conn: sqlite3.Connection,
    user_ids: List[str],
    museums: List[Dict],
    exclude_ids: Tuple[int | None, int | None],
    target_count: int = 70,
) -> int:
    """
    Create a baseline of random interactions across the catalog.
    Excludes specific museum ids (e.g., Louvre/Rodin) so we can control them separately.
    Returns number of interactions inserted.
    """
    cur = conn.cursor()
    museum_pool = [m for m in museums if m["id"] not in exclude_ids]
    if not museum_pool:
        print("NOTE: No remaining museums after excluding special ones; random interactions will all use them.")
        museum_pool = museums

    interaction_types = ["click", "reading", "favorite", "website_visit"]
    n = random.randint(max(50, target_count - 10), max(target_count, 100))

    for _ in range(n):
        user_id = random.choice(user_ids)
        museum = random.choice(museum_pool)
        museum_id = int(museum["id"])
        itype = random.choice(interaction_types)
        if itype == "reading":
            duration = random.uniform(15, 600)  # 15s–10min
        else:
            duration = 0.0
        insert_interaction(cur, user_id, museum_id, itype, duration)

    conn.commit()
    print(f"Inserted {n} random baseline interactions.")
    return n


def seed_biased_feedback(
    conn: sqlite3.Connection,
    user_ids: List[str],
    louvre_id: int | None,
    rodin_id: int | None,
) -> None:
    """
    Strategic bias:
    - Louvre: many interactions, but only ~60% thumbs up.
    - Musée Rodin: few interactions, but 100% thumbs up.
    """
    cur = conn.cursor()

    # Louvre: many interactions, mediocre approval
    if louvre_id is not None:
        n_louvre_interactions = 25
        for _ in range(n_louvre_interactions):
            user_id = random.choice(user_ids)
            itype = random.choice(["click", "reading", "favorite"])
            if itype == "reading":
                duration = random.uniform(30, 600)
            else:
                duration = 0.0
            insert_interaction(cur, user_id, louvre_id, itype, duration)

        # Thumbs: e.g. 10 up, 8 down → ~55% approval
        louvre_users = random.sample(user_ids, min(len(user_ids), 8))
        for uid in louvre_users:
            insert_interaction(cur, uid, louvre_id, "thumbs_down", 0.0)
        for uid in user_ids:
            insert_interaction(cur, uid, louvre_id, "thumbs_up", 0.0)

        print(f"Seeded biased interactions for Louvre (id={louvre_id}).")

    # Rodin: few interactions, perfect approval
    if rodin_id is not None:
        # Small number of views
        rodin_viewers = random.sample(user_ids, min(len(user_ids), 3))
        for uid in rodin_viewers:
            insert_interaction(cur, uid, rodin_id, "click", 0.0)
            insert_interaction(cur, uid, rodin_id, "reading", random.uniform(60, 300))

        # All thumbs up, no thumbs down
        for uid in rodin_viewers:
            insert_interaction(cur, uid, rodin_id, "thumbs_up", 0.0)

        print(f"Seeded biased interactions for Musée Rodin (id={rodin_id}).")

    conn.commit()


def recompute_museum_feedback_aggregates(conn: sqlite3.Connection) -> None:
    """
    Set museums.thumbs_up / thumbs_down based on interactions table so
    the DB is internally consistent with the explicit feedback.
    """
    ensure_feedback_columns(conn)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE museums
        SET
            thumbs_up = (
                SELECT COUNT(*)
                FROM interactions i
                WHERE i.museum_id = museums.id
                  AND i.click_type = 'thumbs_up'
            ),
            thumbs_down = (
                SELECT COUNT(*)
                FROM interactions i
                WHERE i.museum_id = museums.id
                  AND i.click_type = 'thumbs_down'
            )
        """
    )
    conn.commit()
    print("Updated museums.thumbs_up / thumbs_down from interactions.")


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"musea.db not found at {DB_PATH}. Run database_setup.py first.")

    conn = connect_db()
    try:
        ensure_feedback_columns(conn)
        users = create_ghost_users(conn)
        museums, louvre_id, rodin_id = get_museums(conn)
        seed_random_interactions(conn, users, museums, (louvre_id, rodin_id))
        seed_biased_feedback(conn, users, louvre_id, rodin_id)
        recompute_museum_feedback_aggregates(conn)
    finally:
        conn.close()

    print("✅ Fake data seeding complete.")


if __name__ == "__main__":
    main()

