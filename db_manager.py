"""
Musea DB Manager: all SQL and data logic for musea.db.
Single source of truth for users, museums, interactions. Keeps app.py clean.
"""
import sqlite3
import os
import uuid
from typing import List, Dict, Any, Optional

from db_utils import HUB_CITY_COORDS

DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ---- Visitor identity & onboarding ----

def get_or_create_visitor_id(session: dict) -> str:
    """
    Ensure session has a user_id. New visitors get guest_<uuid> and a row in users.
    Returns the current user_id.
    """
    uid = session.get("user_id")
    if uid:
        return uid
    uid = "guest_" + uuid.uuid4().hex[:12]
    session["user_id"] = uid
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (user_id, pseudo, ui_language, visitor_type, distance_pref, interest_mode, theme_pref)
            VALUES (?, ?, '', 'Guest', '', '', NULL)
            """,
            (uid, uid),
        )
        conn.commit()
    finally:
        conn.close()
    return uid


def has_completed_onboarding(user_id: str) -> bool:
    """True if user has a non-guest profile in musea users."""
    if not user_id:
        return False
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT visitor_type FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row is not None and (row["visitor_type"] or "").strip() != "Guest"
    finally:
        conn.close()


def get_user_by_pseudo(pseudo: str) -> Optional[Dict[str, Any]]:
    """Return user row as dict if pseudo exists, else None. Used for login."""
    if not (pseudo or "").strip():
        return None
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE pseudo = ?", (pseudo.strip(),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_user_profile(data: dict) -> None:
    """
    Insert or update user in musea users (onboarding data).
    data must include pseudo; user_id is set to pseudo for new users.
    data: pseudo, ui_language, visitor_type, distance_pref, interest_mode, theme_pref (str or list).
    """
    pseudo = (data.get("pseudo") or "").strip()
    if not pseudo:
        raise ValueError("pseudo is required")
    uid = data.get("user_id") or pseudo
    theme_pref = data.get("theme_pref")
    if isinstance(theme_pref, (list, tuple)):
        theme_pref = ",".join(str(x) for x in theme_pref) if theme_pref else None
    hub_city = (data.get("hub_city") or "").strip() or None
    conn = _conn()
    try:
        # Lightweight migration: ensure hub_city column exists on users
        try:
            conn.execute("ALTER TABLE users ADD COLUMN hub_city TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists or table structure fixed earlier
            pass

        conn.execute(
            """
            INSERT INTO users (user_id, pseudo, ui_language, visitor_type, distance_pref, interest_mode, theme_pref, hub_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                pseudo = excluded.pseudo,
                ui_language = excluded.ui_language,
                visitor_type = excluded.visitor_type,
                distance_pref = excluded.distance_pref,
                interest_mode = excluded.interest_mode,
                theme_pref = excluded.theme_pref,
                hub_city = COALESCE(excluded.hub_city, users.hub_city)
            """,
            (
                uid,
                pseudo,
                data.get("ui_language", ""),
                data.get("visitor_type", ""),
                data.get("distance_pref", ""),
                data.get("interest_mode", ""),
                theme_pref,
                hub_city,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Return one user row as dict or None."""
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---- Interactions ----

def log_interaction(user_id: str, museum_id: int, click_type: str, duration_sec: float = 0) -> None:
    """Write one interaction into interactions (linked to user_id)."""
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO interactions (user_id, museum_id, click_type, duration_sec)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, int(museum_id), click_type, duration_sec),
        )
        conn.commit()
    finally:
        conn.close()


def has_feedback_for_museum(user_id: str, museum_id: int) -> Optional[str]:
    """
    Return existing feedback click_type ('thumbs_up' or 'thumbs_down') if the user
    has already voted for this museum, otherwise None.
    """
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT click_type
            FROM interactions
            WHERE user_id = ?
              AND museum_id = ?
              AND click_type IN ('thumbs_up', 'thumbs_down')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (user_id, int(museum_id)),
        ).fetchone()
        return row["click_type"] if row else None
    finally:
        conn.close()


def submit_feedback(user_id: str, museum_id: int, direction: str) -> Dict[str, Any]:
    """
    Persist explicit feedback (thumbs up/down) for a museum.

    - Ensures at most one vote per (user, museum).
    - Updates museums.thumbs_up / museums.thumbs_down counters.
    - Logs an interaction row with click_type 'thumbs_up' / 'thumbs_down'.
    """
    direction_norm = (direction or "").strip().lower()
    if direction_norm not in ("up", "down", "thumbs_up", "thumbs_down"):
        raise ValueError("direction must be 'up' or 'down'")

    click_type = "thumbs_up" if direction_norm in ("up", "thumbs_up") else "thumbs_down"

    # Enforce single vote per museum per user
    existing = has_feedback_for_museum(user_id, museum_id)
    if existing:
        return {
            "status": "already_voted",
            "existing": existing,
        }

    conn = _conn()
    try:
        cur = conn.cursor()
        # Insert interaction row
        cur.execute(
            """
            INSERT INTO interactions (user_id, museum_id, click_type, duration_sec)
            VALUES (?, ?, ?, 0)
            """,
            (user_id, int(museum_id), click_type),
        )
        # Increment aggregate counters on museums
        if click_type == "thumbs_up":
            cur.execute(
                "UPDATE museums SET thumbs_up = COALESCE(thumbs_up, 0) + 1 WHERE id = ?",
                (int(museum_id),),
            )
        else:
            cur.execute(
                "UPDATE museums SET thumbs_down = COALESCE(thumbs_down, 0) + 1 WHERE id = ?",
                (int(museum_id),),
            )
        conn.commit()

        # Fetch updated aggregates for transparency / hidden-gem logic
        row = cur.execute(
            """
            SELECT
                COALESCE(thumbs_up, 0)   AS thumbs_up,
                COALESCE(thumbs_down, 0) AS thumbs_down,
                (
                    SELECT COUNT(*)
                    FROM interactions i
                    WHERE i.museum_id = museums.id
                ) AS total_interactions
            FROM museums
            WHERE id = ?
            """,
            (int(museum_id),),
        ).fetchone()

        thumbs_up = int(row["thumbs_up"] or 0)
        thumbs_down = int(row["thumbs_down"] or 0)
        total_interactions = int(row["total_interactions"] or 0)
        total_votes = thumbs_up + thumbs_down
        approval = (thumbs_up / total_votes) * 100.0 if total_votes > 0 else None

        return {
            "status": "ok",
            "click_type": click_type,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "total_interactions": total_interactions,
            "approval_rating": approval,
        }
    finally:
        conn.close()


def get_engagement_for_user(user_id: str) -> Dict[str, Any]:
    """
    Compute engagement from interactions for the dashboard.
    Returns: engagement_score (sum duration_sec + 10 per interaction), total_interactions (count).
    """
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT COALESCE(SUM(duration_sec), 0) AS total_sec,
                   COUNT(*) AS total_count
            FROM interactions WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        total_sec = float(rows["total_sec"] or 0)
        count = int(rows["total_count"] or 0)
        # Engagement score: seconds + 10 points per interaction
        engagement_score = int(total_sec) + 10 * count
        return {
            "engagement_score": engagement_score,
            "total_interactions": count,
            "total_duration_sec": total_sec,
        }
    finally:
        conn.close()


def get_theme_affinity_from_interactions(user_id: str) -> Dict[str, float]:
    """
    Compute theme affinity from interactions: join with museums, sum points per theme.
    Points: click/view-details=1, reading=2+floor(duration_sec/30) capped at 20, favorite=3.
    Returns dict theme -> score (e.g. {'Art': 5, 'History': 3}).
    """
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT i.click_type, COALESCE(i.duration_sec, 0) AS duration_sec, m.theme
            FROM interactions i
            JOIN museums m ON m.id = i.museum_id
            WHERE i.user_id = ?
            """,
            (user_id,),
        ).fetchall()
        by_theme: Dict[str, float] = {}
        for r in rows:
            ct = (r["click_type"] or "").strip().lower()
            dur = float(r["duration_sec"] or 0)
            theme = (r["theme"] or "").strip()
            if not theme:
                continue
            if ct in ("click", "view-details"):
                points = 1
            elif ct == "reading":
                points = 2 + min(20, int(dur // 30))
            elif ct in ("favorite", "website_visit"):
                points = 3
            else:
                points = 1
            by_theme[theme] = by_theme.get(theme, 0) + points
        return by_theme
    finally:
        conn.close()


# ---- Museums ----

def get_all_museums() -> List[Dict[str, Any]]:
    """Return all museums as list of dicts (id, name, location, description, theme, image_url, etc.)."""
    conn = _conn()
    try:
        try:
            conn.execute("ALTER TABLE museums ADD COLUMN image_url TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        rows = conn.execute(
            "SELECT id, identifiant, name, region, theme, latitude, longitude, popularity_score, location, description, COALESCE(image_url, '') AS image_url FROM museums ORDER BY name"
        ).fetchall()
        return [_museum_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_museums_by_theme(theme: str) -> List[Dict[str, Any]]:
    """Return museums whose theme matches (case-insensitive). Used by tests and filtering."""
    if not (theme or "").strip():
        return []
    museums = get_all_museums()
    t = theme.strip().lower()
    return [m for m in museums if (m.get("theme") or "").strip().lower() == t]


def get_distinct_themes() -> List[str]:
    """Return sorted list of theme values that exist in museums (for discovery filter)."""
    museums = get_all_museums()
    themes = {((m.get("theme") or "").strip()) for m in museums if (m.get("theme") or "").strip()}
    return sorted(themes)


def get_museum_by_id(museum_id: int) -> Optional[Dict[str, Any]]:
    """Return one museum as dict or None (detail view: full description, opening_hours, website)."""
    conn = _conn()
    try:
        for col in ("website", "image_url"):
            try:
                conn.execute(f"ALTER TABLE museums ADD COLUMN {col} TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        row = conn.execute(
            "SELECT id, identifiant, name, region, theme, latitude, longitude, popularity_score, location, description, website, image_url FROM museums WHERE id = ?",
            (int(museum_id),),
        ).fetchone()
        if not row:
            return None
        d = _museum_row_to_dict(row)
        d["description"] = (row["description"] or "").strip() or d["description"]
        d["opening_hours"] = None
        raw_web = (row["website"] or "").strip()
        d["website"] = raw_web or None
        raw_img = (row["image_url"] or "").strip()
        d["image_url"] = raw_img or None
        return d
    finally:
        conn.close()


def _museum_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Normalize a DB row to template-friendly dict (id, name, location, description, theme, image_url)."""
    d = dict(row)
    raw_img = (d.get("image_url") or "").strip()
    return {
        "id": d["id"],
        "name": d["name"],
        "location": d.get("location") or d.get("region") or "",
        "description": (d.get("description") or "")[:500],
        "theme": d.get("theme"),
        "image_url": raw_img or None,
        "region": d.get("region"),
        "popularity_score": d.get("popularity_score") or 0,
        "latitude": d.get("latitude"),
        "longitude": d.get("longitude"),
    }


def get_museums_sorted_for_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all museums and sort by a simple scoring algorithm:
    - User theme_pref (comma-separated) vs museum.theme → match = higher score.
    - Then by popularity_score, then by name.
    """
    profile = get_user_profile(user_id)
    theme_pref = (profile.get("theme_pref") or "").strip()
    preferred = {t.strip() for t in theme_pref.split(",") if t.strip()}

    museums = get_all_museums()
    if not preferred:
        return sorted(museums, key=lambda m: (-(m.get("popularity_score") or 0), (m.get("name") or "")))

    def score(m: Dict[str, Any]) -> tuple:
        theme = (m.get("theme") or "").strip()
        match = 1 if theme in preferred else 0
        return (-match, -(m.get("popularity_score") or 0), (m.get("name") or ""))

    return sorted(museums, key=score)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometers."""
    from math import radians, sin, cos, sqrt, atan2

    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _annotate_and_filter_by_distance(
    user_id: Optional[str],
    museums: List[Dict[str, Any]],
    max_km: float = 50.0,
) -> List[Dict[str, Any]]:
    """
    Attach `distance_km` to each museum for the given user and,
    then, based on the user's distance preference, keep only museums
    in one of three bands:

    - 'nearby'  → < 20 km
    - 'medium'  → 20–50 km
    - 'far_ok'  → > 50 km
    """
    if not user_id or not museums:
        return museums

    profile = get_user_profile(user_id)
    if not profile:
        return museums

    distance_pref = (profile.get("distance_pref") or "").strip().lower()

    hub_city = (profile.get("hub_city") or "").strip()
    if not hub_city:
        return museums
    hub = next((k for k in HUB_CITY_COORDS.keys() if k.lower() == hub_city.lower()), None)
    if not hub:
        return museums
    lat0, lon0 = HUB_CITY_COORDS[hub]

    annotated: List[Dict[str, Any]] = []
    for m in museums:
        lat = m.get("latitude")
        lon = m.get("longitude")
        if lat is None or lon is None:
            d_km: Optional[float] = None
        else:
            d_km = round(_haversine_km(float(lat), float(lon), float(lat0), float(lon0)))
        m2 = dict(m)
        m2["distance_km"] = d_km
        annotated.append(m2)

    # Apply banded filtering only when we have a known distance preference.
    # Preferences are cumulative:
    # - 'nearby'  → only museums < 20 km
    # - 'medium'  → museums up to 50 km (includes nearby)
    # - 'far_ok'  → all museums with a known distance (includes nearby + medium + far)
    if distance_pref == "nearby":
        annotated = [
            m for m in annotated
            if m.get("distance_km") is not None and m["distance_km"] < 20
        ]
    elif distance_pref == "medium":
        annotated = [
            m for m in annotated
            if m.get("distance_km") is not None and m["distance_km"] <= 50
        ]
    elif distance_pref in ("far_ok", "far"):
        annotated = [
            m for m in annotated
            if m.get("distance_km") is not None
        ]

    return annotated


def _compute_exploration_ratio(
    user_id: str,
    default_ratio: float,
    engagement_score: Optional[int],
) -> float:
    """
    Compute exploration ratio (share of out-of-preference museums) from
    the user's discovery style and engagement.

    - classics     → ≈10% discovery (capped ~15%)
    - balanced     → ≈30% discovery (capped ~35%)
    - hidden_gems  → ≈50% discovery (capped ~55%)
    - fallback     → default_ratio (capped ~25%)
    """
    profile = get_user_profile(user_id)
    interest_mode = (profile.get("interest_mode") or "").strip().lower() if profile else ""

    if interest_mode == "classics":
        base = 0.10
        cap = 0.15
    elif interest_mode == "balanced":
        base = 0.30
        cap = 0.35
    elif interest_mode == "hidden_gems":
        base = 0.50
        cap = 0.55
    else:
        base = default_ratio
        cap = 0.25

    if engagement_score is None:
        engagement_score = get_engagement_for_user(user_id).get("engagement_score", 0)
    bump = min(0.05, engagement_score / 2000.0)
    exploration = base + bump
    return min(cap, max(0.0, exploration))


def get_similar_museums(museum_id: int, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Recommend up to `max_results` museums similar to the given one.

    Heuristic:
    - Prefer same theme.
    - Then same location/region (coarse proximity).
    - Break ties by popularity_score and name.
    """
    base = get_museum_by_id(museum_id)
    if not base:
        return []

    base_theme = (base.get("theme") or "").strip().lower()
    base_location = (base.get("location") or "").strip()
    # City is the part before the first comma in the display location (e.g. "Lyon, Auvergne-Rhône-Alpes" → "lyon")
    base_city = base_location.split(",")[0].strip().lower() if base_location else ""

    candidates = [m for m in get_all_museums() if int(m["id"]) != int(museum_id)]

    # Primary rule: same theme AND exact same location string as displayed.
    strict_matches: List[Dict[str, Any]] = []
    for m in candidates:
        theme = (m.get("theme") or "").strip().lower()
        location = (m.get("location") or "").strip()
        city = location.split(",")[0].strip().lower() if location else ""
        if base_theme and theme and base_theme == theme and base_city and city and base_city == city:
            strict_matches.append(m)

    strict_matches.sort(
        key=lambda m: (
            -(m.get("popularity_score") or 0),
            (m.get("name") or ""),
        )
    )
    if len(strict_matches) >= max_results:
        return strict_matches[:max_results]

    # Fallback: if not enough strict matches, fill with same-theme anywhere.
    remaining = max_results - len(strict_matches)
    theme_matches: List[Dict[str, Any]] = []
    for m in candidates:
        if m in strict_matches:
            continue
        theme = (m.get("theme") or "").strip().lower()
        if base_theme and theme and base_theme == theme:
            theme_matches.append(m)

    theme_matches.sort(
        key=lambda m: (
            -(m.get("popularity_score") or 0),
            (m.get("name") or ""),
        )
    )
    return strict_matches + theme_matches[:remaining]


def get_museums_for_discovery(
    user_id: str,
    max_results: int,
    exploration_ratio: float = 0.2,
    engagement_score: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Discovery mix: ~(1-exploration_ratio) from preferred themes, ~exploration_ratio from others.
    exploration_ratio can adapt with engagement (e.g. more engagement → slightly more exploration).
    """
    if engagement_score is None:
        engagement_score = get_engagement_for_user(user_id).get("engagement_score", 0)
    # Exploration ratio driven by discovery style (classics/balanced/hidden_gems)
    exploration = _compute_exploration_ratio(user_id, exploration_ratio, engagement_score)

    profile = get_user_profile(user_id)
    theme_pref = (profile.get("theme_pref") or "").strip()
    preferred = {t.strip() for t in theme_pref.split(",") if t.strip()}

    # Dynamic affinities from actual interactions (updated in real time)
    theme_aff = get_theme_affinity_from_interactions(user_id)

    # Promote top dynamic themes into the preferred set so the system can
    # gradually shift from onboarding preferences toward what the user really likes.
    if theme_aff:
        top_dynamic = sorted(theme_aff.items(), key=lambda x: -x[1])[:2]
        for t, _ in top_dynamic:
            if t:
                preferred.add(t)

    museums = get_all_museums()
    if not preferred:
        museums = sorted(
            museums,
            key=lambda m: (-(m.get("popularity_score") or 0), (m.get("name") or "")),
        )[:max_results]
        return _annotate_and_filter_by_distance(user_id, museums, max_km=50.0)

    matched = [m for m in museums if (m.get("theme") or "").strip() in preferred]
    others = [m for m in museums if (m.get("theme") or "").strip() not in preferred]

    def dyn_score(m: Dict[str, Any]) -> float:
        t = (m.get("theme") or "").strip()
        return float(theme_aff.get(t, 0.0)) if theme_aff else 0.0

    matched = sorted(
        matched,
        key=lambda m: (
            -dyn_score(m),
            -(m.get("popularity_score") or 0),
            (m.get("name") or ""),
        ),
    )
    others = sorted(
        others,
        key=lambda m: (
            -dyn_score(m),
            -(m.get("popularity_score") or 0),
            (m.get("name") or ""),
        ),
    )

    n_explore = max(1, int(round(max_results * exploration)))
    n_matched = min(len(matched), max_results - n_explore)
    n_explore = min(len(others), max_results - n_matched)
    result = (matched[:n_matched] + others[:n_explore])[:max_results]
    return _annotate_and_filter_by_distance(user_id, result, max_km=50.0)


def get_museums_for_discovery_all(
    user_id: str,
    exploration_ratio: float = 0.2,
    engagement_score: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Discovery ordering for ALL museums:
    - Prioritise museums that match the user's preferred themes.
    - Still keep ~exploration_ratio of other themes interleaved near the top.
    - Return the full list (no truncation), sorted for the discovery page.
    """
    if engagement_score is None:
        engagement_score = get_engagement_for_user(user_id).get("engagement_score", 0)
    # Exploration ratio driven by discovery style (classics/balanced/hidden_gems)
    exploration = _compute_exploration_ratio(user_id, exploration_ratio, engagement_score)

    profile = get_user_profile(user_id)
    theme_pref = (profile.get("theme_pref") or "").strip()
    preferred = {t.strip() for t in theme_pref.split(",") if t.strip()}

    # Dynamic affinities from interactions
    theme_aff = get_theme_affinity_from_interactions(user_id)

    # Promote top dynamic themes into preferred set
    if theme_aff:
        top_dynamic = sorted(theme_aff.items(), key=lambda x: -x[1])[:2]
        for t, _ in top_dynamic:
            if t:
                preferred.add(t)

    museums = get_all_museums()
    if not preferred:
        # No preferences: show all, most popular first.
        museums = sorted(
            museums,
            key=lambda m: (-(m.get("popularity_score") or 0), (m.get("name") or "")),
        )
        return _annotate_and_filter_by_distance(user_id, museums, max_km=50.0)

    matched = [m for m in museums if (m.get("theme") or "").strip() in preferred]
    others = [m for m in museums if (m.get("theme") or "").strip() not in preferred]

    def dyn_score(m: Dict[str, Any]) -> float:
        t = (m.get("theme") or "").strip()
        return float(theme_aff.get(t, 0.0)) if theme_aff else 0.0

    matched = sorted(
        matched,
        key=lambda m: (
            -dyn_score(m),
            -(m.get("popularity_score") or 0),
            (m.get("name") or ""),
        ),
    )
    others = sorted(
        others,
        key=lambda m: (
            -dyn_score(m),
            -(m.get("popularity_score") or 0),
            (m.get("name") or ""),
        ),
    )

    total = len(museums)
    if total == 0:
        return []

    # Mix in some exploration among the *first* cards the user sees.
    front_n = min(40, total)
    step = max(4, int(round(1.0 / max(exploration, 0.05))))  # e.g. exploration 0.2 -> step≈5

    front: List[Dict[str, Any]] = []
    i_m, i_o = 0, 0
    while len(front) < front_n and (i_m < len(matched) or i_o < len(others)):
        pos = len(front)
        # Every `step`-th position, try to inject an exploration museum if available.
        if (pos + 1) % step == 0 and i_o < len(others):
            front.append(others[i_o])
            i_o += 1
        elif i_m < len(matched):
            front.append(matched[i_m])
            i_m += 1
        elif i_o < len(others):
            front.append(others[i_o])
            i_o += 1
        else:
            break

    # Append any remaining matched first, then remaining others.
    remaining = matched[i_m:] + others[i_o:]
    result = front + remaining
    return _annotate_and_filter_by_distance(user_id, result, max_km=50.0)


def get_hidden_gems(
    user_id: Optional[str] = None,
    max_results: int = 30,
    max_total_interactions: int = 10,
) -> List[Dict[str, Any]]:
    """
    Hidden gems for a given user:
    - Only museums whose theme is in the user's theme_pref.
    - Only museums with fewer than `max_total_interactions` total interactions.
    - Sorted by approval rating (thumbs_up %) desc, then by total interactions asc.
    """
    profile = get_user_profile(user_id) if user_id else None
    preferred: set[str] = set()
    if profile:
        theme_pref = (profile.get("theme_pref") or "").strip()
        preferred = {t.strip() for t in theme_pref.split(",") if t.strip()}

    conn = _conn()
    try:
        # Ensure feedback columns exist in case DB was created before migration.
        for sql in (
            "ALTER TABLE museums ADD COLUMN thumbs_up INTEGER DEFAULT 0",
            "ALTER TABLE museums ADD COLUMN thumbs_down INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                pass

        if preferred:
            # User-specific: restrict to preferred themes.
            placeholder = ",".join("?" for _ in preferred)
            params = list(preferred) + [max_total_interactions]
            rows = conn.execute(
                f"""
                SELECT
                    m.id,
                    m.identifiant,
                    m.name,
                    m.region,
                    m.theme,
                    m.latitude,
                    m.longitude,
                    m.popularity_score,
                    m.location,
                    m.description,
                    COALESCE(m.image_url, '') AS image_url,
                    COALESCE(m.thumbs_up, 0)   AS thumbs_up,
                    COALESCE(m.thumbs_down, 0) AS thumbs_down,
                    COALESCE(cnt.total_interactions, 0) AS total_interactions
                FROM museums m
                LEFT JOIN (
                    SELECT museum_id, COUNT(*) AS total_interactions
                    FROM interactions
                    GROUP BY museum_id
                ) AS cnt
                  ON cnt.museum_id = m.id
                WHERE (m.theme IN ({placeholder}))
                  AND (COALESCE(cnt.total_interactions, 0) < ?)
                """,
                params,
            ).fetchall()
        else:
            # Anonymous user or no preferences: global underrated list (no theme filter).
            rows = conn.execute(
                """
                SELECT
                    m.id,
                    m.identifiant,
                    m.name,
                    m.region,
                    m.theme,
                    m.latitude,
                    m.longitude,
                    m.popularity_score,
                    m.location,
                    m.description,
                    COALESCE(m.image_url, '') AS image_url,
                    COALESCE(m.thumbs_up, 0)   AS thumbs_up,
                    COALESCE(m.thumbs_down, 0) AS thumbs_down,
                    COALESCE(cnt.total_interactions, 0) AS total_interactions
                FROM museums m
                LEFT JOIN (
                    SELECT museum_id, COUNT(*) AS total_interactions
                    FROM interactions
                    GROUP BY museum_id
                ) AS cnt
                  ON cnt.museum_id = m.id
                WHERE COALESCE(cnt.total_interactions, 0) < ?
                """,
                (max_total_interactions,),
            ).fetchall()
    finally:
        conn.close()

    def decorate(row: sqlite3.Row) -> Dict[str, Any]:
        base = _museum_row_to_dict(row)
        thumbs_up = int(row["thumbs_up"] or 0)
        thumbs_down = int(row["thumbs_down"] or 0)
        total_interactions = int(row["total_interactions"] or 0)
        total_votes = thumbs_up + thumbs_down
        approval = (thumbs_up / total_votes) * 100.0 if total_votes > 0 else None
        base["thumbs_up"] = thumbs_up
        base["thumbs_down"] = thumbs_down
        base["total_interactions"] = total_interactions
        base["approval_rating"] = approval
        return base

    decorated = [decorate(r) for r in rows]

    def sort_key(m: Dict[str, Any]) -> tuple:
        approval = m.get("approval_rating")
        total_interactions = m.get("total_interactions") or 0
        # Higher approval first; 'None' approval treated as 0
        approval_val = float(approval) if approval is not None else 0.0
        return (-approval_val, total_interactions, (m.get("name") or ""))

    return sorted(decorated, key=sort_key)[:max_results]
