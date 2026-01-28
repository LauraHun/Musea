"""
Musea Phase 1: Database setup and museum import.
Initializes musea.db from schema.sql and imports museums from Museofile CSV.
"""
import sqlite3
import csv
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# Map CSV Domaine_thematique / Categorie to app themes: Art, History, Science, Local Heritage
THEME_KEYWORDS = {
    "Art": ["beaux-arts", "art", "arts décoratifs", "arts decoratifs", "peinture", "sculpture", "art moderne", "art contemporain"],
    "History": ["histoire", "archéologie", "archeologie", "histoire locale", "résistance", "resistance", "déportation", "deportation"],
    "Science": ["sciences", "technique", "industrie", "nature", "sciences de la nature", "physique", "hydroélectricité"],
    "Local Heritage": ["ethnologie", "patrimoine", "heritage", "territoire", "société", "societe", "rural", "ecomusée", "ecomusee"],
}


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _domaine_to_theme(domaine: str) -> str:
    """Map Domaine_thematique string to one of Art, History, Science, Local Heritage."""
    if not domaine:
        return "Local Heritage"  # default
    d = domaine.lower().strip()
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in d:
                return theme
    # first token or default
    first = d.split(",")[0].strip() if "," in d else d
    if "art" in first or "beaux" in first:
        return "Art"
    if "histoire" in first or "archéo" in first:
        return "History"
    if "scien" in first or "techn" in first:
        return "Science"
    return "Local Heritage"


def init_db(db_path: str | None = None) -> None:
    """Initialize musea.db using schema.sql. Adds new columns if missing (migration)."""
    path = db_path or DB_PATH
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = sqlite3.connect(path)
    conn.executescript(schema_sql)
    # Lightweight migrations for incremental columns
    column_alters = [
        "ALTER TABLE museums ADD COLUMN website TEXT",
        "ALTER TABLE museums ADD COLUMN image_url TEXT",
        "ALTER TABLE museums ADD COLUMN thumbs_up INTEGER DEFAULT 0",
        "ALTER TABLE museums ADD COLUMN thumbs_down INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN hub_city TEXT",
    ]
    for sql in column_alters:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            # Column already exists – safe to ignore
            pass
    conn.commit()
    conn.close()
    print(f"Database initialized: {path}")


def import_museums_from_csv(
    csv_path: str,
    db_path: str | None = None,
    encoding: str = "utf-8",
    delimiter: str = ";",
) -> int:
    """
    Import museum dataset from Museofile CSV into museums table.
    CSV columns used: Identifiant, Nom_officiel, Ville, Région, Domaine_thematique,
                     Histoire, Atout, Coordonnees (lat, long), URL (official website).
    Returns the number of rows inserted.
    """
    path = db_path or DB_PATH
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    inserted = 0
    with open(csv_path, "r", encoding=encoding, newline="", errors="replace") as f:
        # Use first line for headers; handle BOM and semicolon
        first_line = f.readline()
        headers_raw = [h.strip().replace("\ufeff", "") for h in first_line.split(delimiter)]
        reader = csv.DictReader(f, fieldnames=headers_raw, delimiter=delimiter, restkey="_extra")

        for row in reader:
            r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k != "_extra"}

            identifiant = (r.get("Identifiant") or "").strip() or None
            name = (r.get("Nom_officiel") or "").strip()
            if not name:
                continue

            region = (r.get("Région") or r.get("Region") or "").strip() or None
            ville = (r.get("Ville") or "").strip()
            location = f"{ville}, {region}" if (ville and region) else (ville or region or "")

            domaine = r.get("Domaine_thematique") or r.get("Domaine thematique") or ""
            theme = _domaine_to_theme(domaine)

            histoire = (r.get("Histoire") or "").strip()
            atout = (r.get("Atout") or "").strip()
            description = (atout or histoire or "")[:2000] or None

            coords = (r.get("Coordonnees") or r.get("Coordonnées") or "").strip()
            latitude, longitude = None, None
            if coords:
                parts = coords.replace(",", " ").split()
                nums = [float(x) for x in parts if _is_float(x)]
                if len(nums) >= 2:
                    latitude, longitude = nums[0], nums[1]

            raw_url = (r.get("URL") or "").strip()
            website = None
            if raw_url:
                website = raw_url if raw_url.startswith("http://") or raw_url.startswith("https://") else "https://" + raw_url

            try:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO museums
                    (identifiant, name, region, theme, latitude, longitude, popularity_score, location, description, website)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                    """,
                    (identifiant, name, region, theme, latitude, longitude, location or None, description, website),
                )
                if cur.rowcount:
                    inserted += 1
                elif identifiant and website is not None:
                    cur.execute("UPDATE museums SET website = ? WHERE identifiant = ?", (website, identifiant))
            except sqlite3.IntegrityError:
                # duplicate identifiant or other constraint
                pass

    conn.commit()
    conn.close()
    print(f"Imported {inserted} museums from {csv_path} into {path}")
    return inserted


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize Musea DB and optionally import museums CSV")
    parser.add_argument("--db", default=DB_PATH, help="Path to musea.db")
    parser.add_argument("--csv", default=None, help="Path to Museofile CSV to import into museums")
    parser.add_argument("--encoding", default="utf-8", help="CSV encoding")
    args = parser.parse_args()

    init_db(args.db)
    if args.csv:
        import_museums_from_csv(args.csv, db_path=args.db, encoding=args.encoding)
