import json
import os
import copy
import uuid
import random
from flask import session
# from flask_session import SqlAlchemySessionInterface, current_app

from version import version_code
from engine import timestamp_now
from version import migrate_loaded_save
from constants import Constant

from bundle import VILLAGES_DIR, SAVES_DIR

__villages = {}  # ALL static neighbors
'''__villages = {
    "USERID_1": {
        "playerInfo": {...},
        "maps": [{...},{...}]
        "privateState": {...}
    },
    "USERID_2": {...}
}'''

__saves = {}  # ALL saved villages
'''__saves = {
    "USERID_1": {
        "playerInfo": {...},
        "maps": [{...},{...}]
        "privateState": {...}
    },
    "USERID_2": {...}
}'''

__initial_village = None

# Load saved villages

from database import db_load_player, db_save_player, db_load_all_saves, db_load_neighbor, db_load_all_neighbors, get_db_connection

def load_saved_villages():
    global __villages
    global __saves
    global __initial_village
    # Empty in memory
    __villages = {}
    __saves = {}
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Load static neighbors from SQLite
        cursor.execute("SELECT nid, map_data FROM neighbor_villages")
        for row in cursor.fetchall():
            nid = row["nid"]
            # Exclude initial template from active neighbors
            if nid == "initial":
                continue
            village = json.loads(row["map_data"])
            __villages[str(nid)] = village
            
        # Load saves from SQLite
        cursor.execute("SELECT pid, save_data FROM players")
        for row in cursor.fetchall():
            pid = row["pid"]
            save = json.loads(row["save_data"])
            __saves[str(pid)] = save
            
        # Load initial template from SQLite
        cursor.execute("SELECT map_data FROM neighbor_villages WHERE nid = 'initial'")
        row = cursor.fetchone()
        if row:
            __initial_village = json.loads(row["map_data"])
        else:
            initial_path = os.path.join(VILLAGES_DIR, "initial.json")
            if os.path.exists(initial_path):
                with open(initial_path, 'r') as f:
                    __initial_village = json.load(f)
                    
        conn.close()
        print(" * Loaded saves and neighbors from SQLite database.")
    except Exception as e:
        print(f" * Error loading saves from SQLite: {e}")
    

# New village

def new_village() -> str:
    global __initial_village
    # Generate USERID
    USERID: str = str(uuid.uuid4())
    assert USERID not in all_userid()
    
    # Load initial template dynamically if not loaded
    if __initial_village is None:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT map_data FROM neighbor_villages WHERE nid = 'initial'")
            row = cursor.fetchone()
            conn.close()
            if row:
                __initial_village = json.loads(row["map_data"])
        except Exception as e:
            print(f" * Error loading initial village template from SQLite: {e}")
            
    # Copy init
    village = copy.deepcopy(__initial_village)
    # Custom values
    village["version"] = version_code
    village["playerInfo"]["pid"] = USERID
    village["maps"][0]["timestamp"] = timestamp_now()
    village["privateState"]["dartsRandomSeed"] = abs(int((2**16 - 1) * random.random()))
    # Memory saves
    __saves[USERID] = village
    # Generate save file in SQLite
    save_session(USERID)
    print("Done.")
    return USERID

# Access functions

def all_saves_userid() -> list:
    "Returns a list of the USERID of every saved village."
    return list(__saves.keys())

def all_userid() -> list:
    "Returns a list of the USERID of every village."
    return list(__villages.keys()) + list(__saves.keys())

def save_info(USERID: str) -> dict:
    save = __saves[USERID]
    default_map = save["playerInfo"]["default_map"]
    empire_name = str(save["playerInfo"]["map_names"][default_map])
    xp = save["maps"][default_map]["xp"]
    level = save["maps"][default_map]["level"]
    return{"userid": USERID, "name": empire_name, "xp": xp, "level": level}

def all_saves_info() -> list:
    saves_info = []
    for userid in __saves:
        saves_info.append(save_info(userid))
    return list(saves_info)

def session(USERID: str) -> dict:
    assert(isinstance(USERID, str))
    return __saves[USERID] if USERID in __saves else None

def neighbor_session(USERID: str) -> dict:
    assert(isinstance(USERID, str))
    if USERID in __saves:
        return __saves[USERID]
    if USERID in __villages:
        return __villages[USERID]

def fb_friends_str(USERID: str) -> list:
    DELETE_ME = [{"uid": "1111", "pic_square":"http://127.0.0.1:5050/img/profile/Paladin_Justiciero.jpg"},
        {"uid": "aa_002", "pic_square":"/1025.png"}]
    friends = []
    # static villages
    for key in __villages:
        vill = __villages[key]
        # Avoid Arthur being loaded as friend.
        if vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_1 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_2 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_3:
            continue
        frie = {}
        frie["uid"] = vill["playerInfo"]["pid"]
        frie["pic_square"] = vill["playerInfo"]["pic"]
        if not frie["pic_square"]: frie["pic_square"] = "/img/profile/1025.png"
        friends += [frie]
    # other players
    for key in __saves:
        vill = __saves[key]
        if vill["playerInfo"]["pid"] == USERID:
            continue
        frie = {}
        frie["uid"] = vill["playerInfo"]["pid"]
        frie["pic_square"] = vill["playerInfo"]["pic"]
        if not frie["pic_square"]: frie["pic_square"] = "/img/profile/1025.png"
        friends += [frie]
    return friends

def neighbors(USERID: str) -> list:
    neighbors = []
    # static villages
    for key in __villages:
        vill = __villages[key]
        # Avoid Arthur being loaded as multiple neigtbors.
        if vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_1 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_2 \
        or vill["playerInfo"]["pid"] == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_3:
            continue
        neigh = vill["playerInfo"]
        neigh["coins"] = vill["maps"][0]["coins"]
        neigh["xp"] = vill["maps"][0]["xp"]
        neigh["level"] = vill["maps"][0]["level"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neigh["wood"] = vill["maps"][0]["wood"]
        neigh["food"] = vill["maps"][0]["food"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neighbors += [neigh]
    # other players
    for key in __saves:
        vill = __saves[key]
        if vill["playerInfo"]["pid"] == USERID:
            continue
        neigh = vill["playerInfo"]
        neigh["coins"] = vill["maps"][0]["coins"]
        neigh["xp"] = vill["maps"][0]["xp"]
        neigh["level"] = vill["maps"][0]["level"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neigh["wood"] = vill["maps"][0]["wood"]
        neigh["food"] = vill["maps"][0]["food"]
        neigh["stone"] = vill["maps"][0]["stone"]
        neighbors += [neigh]
    return neighbors

# Check for valid village
# The reason why this was implemented is to warn the user if a save game from Social Wars was used by accident

def is_valid_village(save: dict):
    if "playerInfo" not in save or "maps" not in save or "privateState" not in save:
        # These are obvious
        return False
    for map in save["maps"]:
        if "oil" in map or "steel" in map:
            return False
        if "stone" not in map or "food" not in map:
            return False
        if "items" not in map:
            return False
        if type(map["items"]) != list:
            return False

    return True

# Persistency

def backup_session(USERID: str):
    # TODO 
    return

def save_session(USERID: str):
    village = session(USERID)
    if not village:
        return
    pid = village["playerInfo"]["pid"]
    name = village["playerInfo"]["name"]
    default_map = village["playerInfo"]["default_map"]
    level = village["maps"][default_map]["level"]
    xp = village["maps"][default_map]["xp"]
    last_logged_in = village["playerInfo"]["last_logged_in"]
    
    db_save_player(pid, name, level, xp, last_logged_in, village)
    print(f" * Saved village '{name}' (Level {level}) to SQLite database.")