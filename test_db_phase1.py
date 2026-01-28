"""
Quick test for Phase 1: schema, database_setup, db_manager.
Run from project root:
  python test_db_phase1.py
Uses db_manager (musea.db) as the app does; db_utils is legacy/deprecated.
"""
import os
import sys

# Project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from database_setup import init_db, import_museums_from_csv, DB_PATH
import db_manager


def test_phase1():
    print("=== Phase 1 DB tests (db_manager) ===\n")

    # 1) Init DB (creates musea.db from schema.sql)
    print("1. Initializing database...")
    init_db()
    assert os.path.exists(DB_PATH), "musea.db was not created"
    print("   OK: musea.db exists\n")

    # 2) Optional: import CSV if file exists
    csv_path = os.path.join(PROJECT_ROOT, "musees-de-france-base-museofile (1).csv")
    if os.path.exists(csv_path):
        print("2. Importing museums from CSV...")
        n = import_museums_from_csv(csv_path)
        print(f"   OK: imported {n} museums\n")
    else:
        print("2. CSV not found, skipping import.\n")

    # 3) save_user_profile (db_manager requires pseudo)
    print("3. Testing save_user_profile...")
    db_manager.save_user_profile({
        "user_id": "test_user_1",
        "pseudo": "test_user_1",
        "ui_language": "English",
        "visitor_type": "Tourist",
        "distance_pref": "medium",
        "interest_mode": "balanced",
        "theme_pref": "Art,History",
    })
    print("   OK: profile saved\n")

    # 4) get_museums_by_theme (requires museums in DB)
    print("4. Testing get_museums_by_theme('Art')...")
    arts = db_manager.get_museums_by_theme("Art")
    print(f"   OK: found {len(arts)} museums with theme Art")
    if arts:
        m = arts[0]
        print(f"   Example: id={m.get('id')}, name={m.get('name')}, theme={m.get('theme')}\n")
    else:
        print("   (No museums in DB yet; run with CSV import first.)\n")

    # 5) log_interaction (museum_id must exist if you use real ID)
    print("5. Testing log_interaction...")
    try:
        db_manager.log_interaction("test_user_1", museum_id=1, click_type="view-details", duration_sec=30.5)
        print("   OK: interaction logged\n")
    except Exception as e:
        print(f"   Note: {e}")
        print("   (Expected if museums table is empty; add museums via CSV import.)\n")

    print("=== Phase 1 tests done ===")


if __name__ == "__main__":
    test_phase1()
