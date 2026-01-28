"""
Musea Phase 1: DB helper utilities (LEGACY).
Uses standard library sqlite3. DB path: musea.db in project root.

DEPRECATED: The app uses db_manager.py for all musea.db operations (users with pseudo,
museums, interactions, theme affinity). This module is kept only for reference; use
db_manager for new code. test_db_phase1.py has been updated to use db_manager.
"""
import sqlite3
import os
from typing import List, Dict, Any, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")

# Hub cities (approximate coordinates; WGS84, degrees)
HUB_CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "Lyon": (45.7640, 4.8357),
    "Clermont-Ferrand": (45.7772, 3.0870),
    "Saint-Étienne": (45.4397, 4.3872),
    "Saint-Etienne": (45.4397, 4.3872),  # allow both spellings
    "Grenoble": (45.1885, 5.7245),
}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_user_profile(data: dict) -> None:
    """
    Save or update user profile from onboarding.
    data: dict with keys user_id, ui_language, visitor_type, distance_pref, interest_mode,
          and optionally theme_pref (str, e.g. comma-separated "Art,History").
    """
    conn = _connect()
    cur = conn.cursor()
    user_id = data.get("user_id")
    if not user_id:
        conn.close()
        raise ValueError("user_id is required")
    theme_pref = data.get("theme_pref")
    if isinstance(theme_pref, (list, tuple)):
        theme_pref = ",".join(str(x) for x in theme_pref) if theme_pref else None
    cur.execute(
        """
        INSERT INTO users (user_id, ui_language, visitor_type, distance_pref, interest_mode, theme_pref)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            ui_language = excluded.ui_language,
            visitor_type = excluded.visitor_type,
            distance_pref = excluded.distance_pref,
            interest_mode = excluded.interest_mode,
            theme_pref = excluded.theme_pref
        """,
        (
            user_id,
            data.get("ui_language", ""),
            data.get("visitor_type", ""),
            data.get("distance_pref", ""),
            data.get("interest_mode", ""),
            theme_pref,
        ),
    )
    conn.commit()
    conn.close()


def get_museums_by_theme(theme: str) -> List[Dict[str, Any]]:
    """
    Return museums whose theme matches (case-insensitive).
    Returns list of dicts with keys id, name, region, theme, latitude, longitude,
    popularity_score, location, description, etc.
    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM museums WHERE LOWER(TRIM(theme)) = LOWER(TRIM(?))", (theme,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_interaction(user_id: str, museum_id: int, click_type: str, duration: float = 0) -> None:
    """
    Log an interaction: click_type, museum_id, user_id, duration_sec.
    click_type: e.g. 'view-details', 'favorite', 'reading'.
    duration: duration_sec (e.g. seconds on page).
    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO interactions (user_id, museum_id, click_type, duration_sec)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, museum_id, click_type, duration),
    )
    conn.commit()
    conn.close()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute great-circle distance between two points on Earth (in kilometers)
    using the Haversine formula.
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371.0  # Earth radius in km
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def get_distance_to_museum(user_hub_city: str, museum_id: int, db_path: Optional[str] = None) -> Optional[float]:
    """
    Return the distance in kilometers between a hub city and the given museum.

    - `user_hub_city` must match a key in HUB_CITY_COORDS (case-insensitive).
    - Uses the museum's latitude/longitude columns imported from the CSV.
    - Returns None if coordinates are missing or hub city is unknown.
    """
    if not user_hub_city:
        return None

    # Normalise hub key
    hub_key = None
    name_l = user_hub_city.strip().lower()
    for key in HUB_CITY_COORDS.keys():
        if key.lower() == name_l:
            hub_key = key
            break
    if hub_key is None:
        return None

    lat0, lon0 = HUB_CITY_COORDS[hub_key]

    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor();
        row = cur.execute(
            "SELECT latitude, longitude FROM museums WHERE id = ?",
            (int(museum_id),),
        ).fetchone()
        if not row:
            return None
        lat, lon = row
        if lat is None or lon is None:
            return None
        return _haversine_km(float(lat), float(lon), float(lat0), float(lon0))
    finally:
        conn.close()
