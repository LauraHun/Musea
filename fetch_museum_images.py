"""
Fetch a representative image for each museum from Wikipedia, Wikidata, or theme fallbacks.
Run: python fetch_museum_images.py [--limit N]

1. Tries French then English Wikipedia (pageimages).
2. Falls back to Wikidata (P18 image) -> Commons thumbnail.
3. If still none, uses theme-based default images (Art, History, Science, Local Heritage).
"""
import argparse
import sqlite3
import urllib.request
import urllib.parse
import json
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")
WIKI_API_FR = "https://fr.wikipedia.org/w/api.php"
WIKI_API_EN = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
THUMB_SIZE = 640
REQUEST_DELAY_SEC = 0.25  # be nice to APIs

# Theme-based default images (Unsplash; free to use, no API key)
THEME_DEFAULT_IMAGES = {
    "Art": "https://images.unsplash.com/photo-1536924940846-227afb31e2a5?w=640",
    # History: shelves of archival books / documents
    "History": "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=640",
    "Science": "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=640",
    "Local Heritage": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=640",
}


def _api_get(url_base: str, params: dict) -> dict:
    url = url_base + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Musea/1.0 (museum explorer; educational)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def search_wikipedia(query: str, api_base: str) -> list[int]:
    """Search Wikipedia; return list of page IDs (best first)."""
    try:
        data = _api_get(api_base, {
            "action": "query",
            "list": "search",
            "srsearch": query[:200],
            "format": "json",
            "srlimit": 5,
        })
        return [int(h["pageid"]) for h in data.get("query", {}).get("search", [])]
    except Exception:
        return []


def get_page_image_url(page_id: int, api_base: str) -> str | None:
    """Get the main image URL for a Wikipedia page (thumbnail)."""
    try:
        data = _api_get(api_base, {
            "action": "query",
            "pageids": page_id,
            "prop": "pageimages",
            "pithumbsize": THUMB_SIZE,
            "piprop": "thumbnail|original",
            "format": "json",
        })
        pages = data.get("query", {}).get("pages", {})
        p = pages.get(str(page_id), {})
        thumb = p.get("thumbnail", {}) or p.get("original", {})
        src = thumb.get("source") if isinstance(thumb, dict) else None
        return (src or "").strip() or None
    except Exception:
        return None


def fetch_wikipedia_image(query: str) -> str | None:
    """Try FR then EN Wikipedia; return image URL or None."""
    for api_base in (WIKI_API_FR, WIKI_API_EN):
        time.sleep(REQUEST_DELAY_SEC)
        page_ids = search_wikipedia(query, api_base)
        for pid in page_ids:
            time.sleep(REQUEST_DELAY_SEC)
            url = get_page_image_url(pid, api_base)
            if url:
                return url
    return None


def fetch_wikidata_image(query: str) -> str | None:
    """Search Wikidata for museum, get P18 (image), return Commons thumbnail URL."""
    try:
        time.sleep(REQUEST_DELAY_SEC)
        data = _api_get(WIKIDATA_API, {
            "action": "wbsearchentities",
            "search": query[:200],
            "language": "fr",
            "limit": 5,
            "format": "json",
        })
        entities = data.get("search", [])
        for e in entities:
            qid = e.get("id")
            if not qid:
                continue
            time.sleep(REQUEST_DELAY_SEC)
            edata = _api_get(WIKIDATA_API, {
                "action": "wbgetentities",
                "ids": qid,
                "props": "claims",
                "format": "json",
            })
            claims = edata.get("entities", {}).get(qid, {}).get("claims", {})
            p18 = claims.get("P18", [])
            if not p18:
                continue
            fn = p18[0].get("mainsnak", {}).get("datavalue", {}).get("value")
            if not fn:
                continue
            # Commons Special:FilePath returns a redirect to the image URL
            enc = urllib.parse.quote(fn.replace(" ", "_"))
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{enc}?width={THUMB_SIZE}"
    except Exception:
        pass
    return None


def build_search_query(name: str, location: str) -> str:
    """Build a search string: museum name + city/region + France."""
    name = (name or "").strip()
    loc = (location or "").strip()
    if "," in loc:
        loc = loc.split(",")[0].strip()
    parts = [name, loc, "France"] if name else [loc, "France"] if loc else ["France"]
    return " ".join(p for p in parts if p)


def theme_fallback(theme: str | None) -> str:
    """Return theme-based default image URL. Unknown theme -> History generic."""
    t = (theme or "").strip()
    return THEME_DEFAULT_IMAGES.get(t) or THEME_DEFAULT_IMAGES["History"]


def main(db_path: str | None = None, limit: int | None = None, theme_only: bool = False) -> None:
    path = db_path or DB_PATH
    if not os.path.exists(path):
        print(f"Database not found: {path}. Run database_setup.py first.")
        return

    conn = sqlite3.connect(path)
    try:
        try:
            conn.execute("ALTER TABLE museums ADD COLUMN image_url TEXT")
            conn.commit()
        except Exception:
            pass

        sql = "SELECT id, name, location, theme FROM museums ORDER BY id"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        cur = conn.execute(sql)
        rows = cur.fetchall()
        updated_wiki, updated_wd, updated_theme = 0, 0, 0
        for row in rows:
            mid, name, location, theme = row[0], row[1], row[2], (row[3] if len(row) > 3 else None) or ""
            if not name:
                continue
            if theme_only:
                url = theme_fallback(theme)
                conn.execute("UPDATE museums SET image_url = ? WHERE id = ?", (url, mid))
                updated_theme += 1
                print(f"  [{mid}] {name[:50]}... -> theme")
                continue
            query = build_search_query(name, location or "")
            if not query:
                url = theme_fallback(theme)
                conn.execute("UPDATE museums SET image_url = ? WHERE id = ?", (url, mid))
                updated_theme += 1
                print(f"  [{mid}] {name[:50]}... -> theme fallback")
                continue
            url = fetch_wikipedia_image(query)
            if url:
                conn.execute("UPDATE museums SET image_url = ? WHERE id = ?", (url, mid))
                updated_wiki += 1
                print(f"  [{mid}] {name[:50]}... -> Wikipedia")
                continue
            url = fetch_wikidata_image(query)
            if url:
                conn.execute("UPDATE museums SET image_url = ? WHERE id = ?", (url, mid))
                updated_wd += 1
                print(f"  [{mid}] {name[:50]}... -> Wikidata")
                continue
            url = theme_fallback(theme)
            conn.execute("UPDATE museums SET image_url = ? WHERE id = ?", (url, mid))
            updated_theme += 1
            print(f"  [{mid}] {name[:50]}... -> theme fallback")
        conn.commit()
        print(f"Done. Wikipedia: {updated_wiki}, Wikidata: {updated_wd}, theme fallback: {updated_theme}.")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch museum images from Wikipedia/Wikidata or theme fallbacks.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of museums to process (default: all)")
    parser.add_argument("--db", type=str, default=None, help="Path to musea.db (default: ./musea.db)")
    parser.add_argument("--theme-only", action="store_true", help="Skip API calls; assign theme-based images only (fast)")
    args = parser.parse_args()
    main(db_path=args.db, limit=args.limit, theme_only=args.theme_only)
