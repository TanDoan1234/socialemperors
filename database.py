import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "social_empires.db")
VILLAGES_DIR = os.path.join(os.path.dirname(__file__), "villages")
SAVES_DIR = os.path.join(os.path.dirname(__file__), "saves")
QUESTS_DIR = os.path.join(VILLAGES_DIR, "quests")

def get_db_connection():
    """Establish a connection to the SQLite database with row factory for dictionary-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize SQLite tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Players table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            pid TEXT PRIMARY KEY,
            name TEXT,
            level INTEGER,
            xp INTEGER,
            last_logged_in INTEGER,
            save_data TEXT
        )
    """)
    
    # 2. Neighbor villages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS neighbor_villages (
            nid TEXT PRIMARY KEY,
            name TEXT,
            level INTEGER,
            map_data TEXT
        )
    """)
    
    # 3. Quests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            qid INTEGER PRIMARY KEY,
            quest_data TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def migrate_json_to_sqlite():
    """Migrate legacy JSON files into SQLite tables if they are not already present."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Migrate player saves
    if os.path.exists(SAVES_DIR) and os.path.isdir(SAVES_DIR):
        for file in os.listdir(SAVES_DIR):
            if file.endswith(".save.json"):
                file_path = os.path.join(SAVES_DIR, file)
                try:
                    with open(file_path, 'r') as f:
                        save = json.load(f)
                    pid = save["playerInfo"]["pid"]
                    name = save["playerInfo"]["name"]
                    default_map = save["playerInfo"]["default_map"]
                    level = save["maps"][default_map]["level"]
                    xp = save["maps"][default_map]["xp"]
                    last_logged_in = save["playerInfo"]["last_logged_in"]
                    save_data = json.dumps(save)
                    
                    # Insert if not exists
                    cursor.execute("""
                        INSERT OR IGNORE INTO players (pid, name, level, xp, last_logged_in, save_data)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (str(pid), name, level, xp, last_logged_in, save_data))
                except Exception as e:
                    print(f" [DB MIGRATION] Failed to migrate save {file}: {e}")
                    
    # 2. Migrate neighbor villages
    if os.path.exists(VILLAGES_DIR) and os.path.isdir(VILLAGES_DIR):
        for file in os.listdir(VILLAGES_DIR):
            if file == "initial.json" or not file.endswith(".json"):
                continue
            file_path = os.path.join(VILLAGES_DIR, file)
            try:
                with open(file_path, 'r') as f:
                    village = json.load(f)
                nid = village["playerInfo"]["pid"]
                name = village["playerInfo"]["name"]
                level = village["maps"][0]["level"]
                map_data = json.dumps(village)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO neighbor_villages (nid, name, level, map_data)
                    VALUES (?, ?, ?, ?)
                """, (str(nid), name, level, map_data))
            except Exception as e:
                print(f" [DB MIGRATION] Failed to migrate village {file}: {e}")

    # 3. Migrate quest maps
    if os.path.exists(QUESTS_DIR) and os.path.isdir(QUESTS_DIR):
        for file in os.listdir(QUESTS_DIR):
            if file.endswith(".json"):
                file_path = os.path.join(QUESTS_DIR, file)
                try:
                    qid = int(os.path.splitext(file)[0])
                    with open(file_path, 'r') as f:
                        quest = json.load(f)
                    quest_data = json.dumps(quest)
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO quests (qid, quest_data)
                        VALUES (?, ?)
                    """, (qid, quest_data))
                except Exception as e:
                    print(f" [DB MIGRATION] Failed to migrate quest {file}: {e}")
                    
    # 4. Migrate initial village template
    initial_path = os.path.join(VILLAGES_DIR, "initial.json")
    if os.path.exists(initial_path):
        try:
            with open(initial_path, 'r') as f:
                initial = json.load(f)
            cursor.execute("""
                INSERT OR REPLACE INTO neighbor_villages (nid, name, level, map_data)
                VALUES (?, ?, ?, ?)
            """, ("initial", "Initial Template", 1, json.dumps(initial)))
        except Exception as e:
            print(f" [DB MIGRATION] Failed to migrate initial.json: {e}")

    conn.commit()
    conn.close()
    print(" [DB MIGRATION] Migration check complete. SQLite Database is ready.")

# --- Database Access Layer ---

def db_load_player(pid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT save_data FROM players WHERE pid = ?", (str(pid),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row["save_data"])
    return None

def db_save_player(pid, name, level, xp, last_logged_in, save):
    conn = get_db_connection()
    cursor = conn.cursor()
    save_data = json.dumps(save)
    cursor.execute("""
        INSERT OR REPLACE INTO players (pid, name, level, xp, last_logged_in, save_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (str(pid), name, level, xp, last_logged_in, save_data))
    conn.commit()
    conn.close()

def db_load_all_saves():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pid, name, level, xp FROM players")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def db_load_neighbor(nid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT map_data FROM neighbor_villages WHERE nid = ?", (str(nid),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row["map_data"])
    return None

def db_load_all_neighbors():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT map_data FROM neighbor_villages")
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row["map_data"]) for row in rows]

def db_load_quest(qid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT quest_data FROM quests WHERE qid = ?", (qid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row["quest_data"])
    return None
