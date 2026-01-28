"""
Update website column for existing museums from CSV.
Run this when the Flask app is stopped to avoid database locks.
"""
import sqlite3
import csv
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")

def update_websites_from_csv(csv_path: str):
    """Update website column for existing museums by matching identifiant or name."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    updated = 0
    with open(csv_path, "r", encoding="utf-8", newline="", errors="replace") as f:
        first_line = f.readline()
        headers_raw = [h.strip().replace("\ufeff", "") for h in first_line.split(";")]
        reader = csv.DictReader(f, fieldnames=headers_raw, delimiter=";", restkey="_extra")
        
        for row in reader:
            r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k != "_extra"}
            
            identifiant = (r.get("Identifiant") or "").strip() or None
            name = (r.get("Nom_officiel") or "").strip()
            raw_url = (r.get("URL") or "").strip()
            
            if not raw_url or not name:
                continue
            
            website = raw_url if raw_url.startswith("http://") or raw_url.startswith("https://") else "https://" + raw_url
            
            # Try to update by identifiant first, then by name
            if identifiant:
                cur.execute("UPDATE museums SET website = ? WHERE identifiant = ?", (website, identifiant))
                if cur.rowcount > 0:
                    updated += 1
                    continue
            
            # Fallback: match by name
            cur.execute("UPDATE museums SET website = ? WHERE name = ? AND (website IS NULL OR website = '')", (website, name))
            if cur.rowcount > 0:
                updated += 1
    
    conn.commit()
    conn.close()
    print(f"Updated website for {updated} museums")
    return updated

if __name__ == "__main__":
    csv_file = "musees-de-france-base-museofile (1).csv"
    if os.path.exists(csv_file):
        update_websites_from_csv(csv_file)
    else:
        print(f"CSV file not found: {csv_file}")
        print("Please provide the CSV file path as an argument or ensure it's in the current directory")
