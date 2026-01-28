-- Musea Phase 1 Schema
-- Database: musea.db

-- Users: profile info from onboarding; pseudo = login identifier (unique)
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    pseudo TEXT UNIQUE NOT NULL,
    ui_language TEXT NOT NULL,
    visitor_type TEXT NOT NULL,
    distance_pref TEXT NOT NULL,
    interest_mode TEXT NOT NULL,
    theme_pref TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Museums: matches Museofile CSV structure (name, region, theme, lat/long, popularity)
CREATE TABLE IF NOT EXISTS museums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifiant TEXT UNIQUE,
    name TEXT NOT NULL,
    region TEXT,
    theme TEXT,
    latitude REAL,
    longitude REAL,
    popularity_score INTEGER DEFAULT 0,
    location TEXT,
    description TEXT,
    website TEXT,
    image_url TEXT,
    thumbs_up INTEGER DEFAULT 0,
    thumbs_down INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Interactions: click_type, museum_id, user_id, duration_sec
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    museum_id INTEGER NOT NULL,
    click_type TEXT NOT NULL,
    duration_sec REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (museum_id) REFERENCES museums(id)
);

CREATE INDEX IF NOT EXISTS idx_museums_theme ON museums(theme);
CREATE INDEX IF NOT EXISTS idx_museums_region ON museums(region);
CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_museum ON interactions(museum_id);

-- Optional: speed up feedback uniqueness checks (one vote per user/museum)
CREATE INDEX IF NOT EXISTS idx_interactions_feedback ON interactions(user_id, museum_id, click_type);
