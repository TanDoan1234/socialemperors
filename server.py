print (" [+] Loading basics...")
import os
import json
import urllib
import urllib.request
import urllib.error
if os.name == 'nt':
    os.system("color")
    os.system("title Social Empires Server")
else:
    import sys
    sys.stdout.write("\x1b]2;Social Empires Server\x07")

print (" [+] Loading game config...")
from get_game_config import get_game_config, patch_game_config

print (" [+] Loading players...")
from database import migrate_json_to_sqlite
migrate_json_to_sqlite()

from get_player_info import get_player_info, get_neighbor_info
from sessions import load_saved_villages, all_saves_userid, all_saves_info, save_info, new_village, fb_friends_str
load_saved_villages()

print (" [+] Loading server...")
from flask import Flask, render_template, send_from_directory, request, redirect, session
from flask.debughelpers import attach_enctype_error_multidict
from command import command
from engine import timestamp_now
from version import version_name
from constants import Constant
from quests import get_quest_map
from bundle import ASSETS_DIR, STUB_DIR, TEMPLATES_DIR, BASE_DIR

host = '127.0.0.1'
port = 5050

app = Flask(__name__, template_folder=TEMPLATES_DIR)

print (" [+] Configuring server routes...")

force_sync_players = set()

##########
# ROUTES #
##########

## PAGES AND RESOURCES

@app.route("/", methods=['GET', 'POST'])
def login():
    # Log out previous session
    session.pop('USERID', default=None)
    session.pop('GAMEVERSION', default=None)
    # Reload saves. Allows saves modification without server reset
    load_saved_villages()
    # If logging in, set session USERID, and go to play
    if request.method == 'POST':
        session['USERID'] = request.form['USERID']
        session['GAMEVERSION'] = request.form['GAMEVERSION']
        print("[LOGIN] USERID:", request.form['USERID'])
        print("[LOGIN] GAMEVERSION:", request.form['GAMEVERSION'])
        return redirect("/play.html")
    # Login page
    if request.method == 'GET':
        saves_info = all_saves_info()
        return render_template("login.html", saves_info=saves_info, version=version_name)

@app.route("/play.html")
def play():
    print(session)

    if 'USERID' not in session:
        return redirect("/")
    if 'GAMEVERSION' not in session:
        return redirect("/")

    if session['USERID'] not in all_saves_userid():
        return redirect("/")
    
    USERID = session['USERID']
    GAMEVERSION = session['GAMEVERSION']
    print("[PLAY] USERID:", USERID)
    print("[PLAY] GAMEVERSION:", GAMEVERSION)
    return render_template("play.html", save_info=save_info(USERID), serverTime=timestamp_now(), friendsInfo=fb_friends_str(USERID), version=version_name, GAMEVERSION=GAMEVERSION, SERVERIP=host)

@app.route("/ruffle.html")
def ruffle():
    print(session)

    if 'USERID' not in session:
        return redirect("/")
    if 'GAMEVERSION' not in session:
        return redirect("/")

    if session['USERID'] not in all_saves_userid():
        return redirect("/")
    
    USERID = session['USERID']
    GAMEVERSION = session['GAMEVERSION']
    print("[RUFFLE] USERID:", USERID)
    print("[RUFFLE] GAMEVERSION:", GAMEVERSION)
    return render_template("ruffle.html", save_info=save_info(USERID), serverTime=timestamp_now(), version=version_name, GAMEVERSION=GAMEVERSION, SERVERIP=host)


@app.route("/new.html")
def new():
    session['USERID'] = new_village()
    session['GAMEVERSION'] = "SocialEmpires0926bsec.swf"
    return redirect("play.html")

@app.route("/crossdomain.xml")
def crossdomain():
    return send_from_directory(STUB_DIR, "crossdomain.xml")

@app.route("/img/<path:path>")
def images(path):
    return send_from_directory(TEMPLATES_DIR + "/img", path)

@app.route("/css/<path:path>")
def css(path):
    return send_from_directory(TEMPLATES_DIR + "/css", path)

## GAME STATIC


@app.route("/default01.static.socialpointgames.com/static/socialempires/swf/05122012_projectiles.swf")
def similar_05122012_projectiles():
    return send_from_directory(ASSETS_DIR + "/swf", "20130417_projectiles.swf")

@app.route("/default01.static.socialpointgames.com/static/socialempires/swf/05122012_magicParticles.swf")
def similar_05122012_magicParticles():
    return send_from_directory(ASSETS_DIR + "/swf", "20131010_magicParticles.swf")

@app.route("/default01.static.socialpointgames.com/static/socialempires/swf/05122012_dynamic.swf")
def similar_05122012_dynamic():
    return send_from_directory(ASSETS_DIR + "/swf", "120608_dynamic.swf")

@app.route("/default01.static.socialpointgames.com/static/socialempires/<path:path>")
def static_assets_loader(path):
    # return send_from_directory(ASSETS_DIR, path)
    if not os.path.exists(ASSETS_DIR + "/"+ path):
        # File does not exists in provided assets
        if not os.path.exists(f"{BASE_DIR}/download_assets/assets/{path}"):
            # Download file from SP's CDN if it doesn't exist

            # Make directory
            directory = os.path.dirname(f"{BASE_DIR}/download_assets/assets/{path}")
            if not os.path.exists(directory):
                os.makedirs(directory)

            # Download File
            URL = f"https://static.socialpointgames.com/static/socialempires/assets/{path}"
            try:
                response = urllib.request.urlretrieve(URL, f"{BASE_DIR}/download_assets/assets/{path}")
            except urllib.error.HTTPError:
                return ("", 404)

            print(f"====== DOWNLOADED ASSET: {URL}")
            return send_from_directory("{BASE_DIR}/download_assets/assets", path)
        else:
            # Use downloaded CDN asset
            print(f"====== USING EXTERNAL: download_assets/assets/{path}")
            return send_from_directory("{BASE_DIR}/download_assets/assets", path)
    else:
        # Use provided asset
        return send_from_directory(ASSETS_DIR, path)

## GAME DYNAMIC

@app.route("/dynamic.flash1.dev.socialpoint.es/appsfb/socialempiresdev/srvempires/track_game_status.php", methods=['POST'])
def track_game_status_response():
    status = request.values['status']
    installId = request.values['installId']
    user_id = request.values['user_id']

    print(f"track_game_status: status={status}, installId={installId}, user_id={user_id}. --", request.values)
    return ("", 200)

@app.route("/dynamic.flash1.dev.socialpoint.es/appsfb/socialempiresdev/srvempires/get_game_config.php", methods=['GET','POST'])
def get_game_config_response():
    spdebug = None

    USERID = request.values['USERID']
    user_key = request.values['user_key']
    if 'spdebug' in request.values:
        spdebug = request.values['spdebug']
    language = request.values['language']

    print(f"get_game_config: USERID: {USERID}. --", request.values)
    
    config = get_game_config()
    
    from sessions import session
    save = session(USERID)
    if save:
        player_info = save.get("playerInfo", {})
        default_map = player_info.get("default_map", 0)
        maps = save.get("maps", [])
        if len(maps) > default_map:
            map_data = maps[default_map]
            pop_bonus = int(map_data.get("increasedPopulation", 0))
            if pop_bonus > 0:
                import copy
                config = copy.deepcopy(config)
                for item in config.get("items", []):
                    if str(item.get("id")) == "26":
                        item["population"] = str(5 + pop_bonus)
                        print(f" [GM CONFIG] Applied custom Town Hall population: {item['population']} for USERID: {USERID}")
                        break
                        
    return config

@app.route("/dynamic.flash1.dev.socialpoint.es/appsfb/socialempiresdev/srvempires/get_player_info.php", methods=['POST'])
def get_player_info_response():

    USERID = request.values['USERID']
    user_key = request.values['user_key']
    spdebug = request.values['spdebug'] if 'spdebug' in request.values else None
    language = request.values['language']
    neighbors = request.values['neighbors'] if 'neighbors' in request.values else None
    client_id = request.values['client_id']
    user = request.values['user'] if 'user' in request.values else None
    map = int(request.values['map']) if 'map' in request.values else None

    print(f"get_player_info: USERID: {USERID}. user: {user} --", request.values)

    # Current Player
    if user is None:
        return (get_player_info(USERID), 200)
    # Arthur
    elif user == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_1 \
    or user == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_2 \
    or user == Constant.NEIGHBOUR_ARTHUR_GUINEVERE_3:
        return (get_neighbor_info(user, map), 200)
    # Quest
    elif user.startswith("100000"): # Dirty but quick
        return get_quest_map(user)
    # Neighbor
    else:
        return (get_neighbor_info(user, map), 200)

@app.route("/dynamic.flash1.dev.socialpoint.es/appsfb/socialempiresdev/srvempires/sync_error_track.php", methods=['POST'])
def sync_error_track_response():
    spdebug = None

    USERID = request.values['USERID']
    user_key = request.values['user_key']
    if 'spdebug' in request.values:
        spdebug = request.values['spdebug']
    language = request.values['language']
    error = request.values['error']
    current_failed = request.values['current_failed']
    tries = request.values['tries'] if 'tries' in request.values else None
    survival = request.values['survival']
    previous_failed = request.values['previous_failed']
    description = request.values['description']
    user_id = request.values['user_id']

    print(f"sync_error_track: USERID: {USERID}. [Error: {error}] tries: {tries}. --", request.values)
    return ("", 200)

@app.route("/null")
def flash_sync_error_response():
    sp_ref_cat = request.values['sp_ref_cat']

    if sp_ref_cat == "flash_sync_error":
        reason = "reload On Sync Error"
    elif sp_ref_cat == "flash_reload_quest":
        reason = "reload On End Quest"
    elif sp_ref_cat == "flash_reload_attack":
        reason = "reload On End Attack"

    print("flash_sync_error", reason, ". --", request.values)
    return redirect("/play.html")

@app.route("/dynamic.flash1.dev.socialpoint.es/appsfb/socialempiresdev/srvempires/command.php", methods=['POST'])
def command_response():
    spdebug = None

    USERID = request.values['USERID']
    user_key = request.values['user_key']
    if 'spdebug' in request.values:
        spdebug = request.values['spdebug']
    language = request.values['language']
    client_id = request.values['client_id']

    print(f"command: USERID: {USERID}. --", request.values)

    data_str = request.values['data']
    data_hash = data_str[:64]
    assert data_str[64] == ';'
    data_payload = data_str[65:]
    data = json.loads(data_payload)

    if USERID in force_sync_players:
        force_sync_players.remove(USERID)
        print(f" [GM SYNC] Forcing client reload for USERID: {USERID}")
        return ({"result": "error", "reason": "GM Force Sync"}, 400)

    command(USERID, data)
    
    return ({"result": "success"}, 200)

@app.route("/dynamic.flash1.dev.socialpoint.es/appsfb/socialempiresdev/srvempires/get_continent_ranking.php")
def get_continent_ranking_response():

    USERID = request.values['USERID']
    worldChange = request.values['worldChange']
    if 'spdebug' in request.values:
        spdebug = request.values['spdebug']
    town_id = request.values['map']
    user_key = request.values['user_key']

    # TODO - stub
    response = {
        "world_id": 0,
        "continent": [
            {"posicion": 0, "nivel": 1, "user_id": 1111}, # villages/AcidCaos
            {"posicion": 1, "nivel": 0},
            {"posicion": 2, "nivel": 0},
            {"posicion": 3, "nivel": 0},
            {"posicion": 4, "nivel": 0},
            {"posicion": 5, "nivel": 0},
            {"posicion": 6, "nivel": 0},
            {"posicion": 7, "nivel": 0}
        ]
    }
    return(response)


#########################
# GM / ADMIN API ROUTES #
#########################

@app.route("/admin")
@app.route("/admin.html")
def admin_page():
    return render_template("admin.html")

@app.route("/assets/<path:path>")
def serve_assets(path):
    return send_from_directory(ASSETS_DIR, path)

@app.route("/api/admin/players")
def admin_players():
    from database import get_db_connection
    from sessions import session
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pid, name, level, xp FROM players")
    db_players = cursor.fetchall()
    conn.close()
    
    players_data = []
    for p in db_players:
        pid = p["pid"]
        save = session(pid)
        if save:
            player_info = save.get("playerInfo", {})
            default_map = player_info.get("default_map", 0)
            map_data = save["maps"][default_map] if len(save.get("maps", [])) > default_map else {}
            players_data.append({
                "pid": pid,
                "name": player_info.get("name", p["name"]),
                "level": map_data.get("level", player_info.get("level", p["level"])),
                "xp": map_data.get("xp", player_info.get("xp", p["xp"])),
                "coins": map_data.get("coins", player_info.get("coins", 0)),
                "cash": player_info.get("cash", 0),
                "wood": map_data.get("wood", 0),
                "stone": map_data.get("stone", 0),
                "food": map_data.get("food", 0),
                "expansions": map_data.get("expansions", []),
                "completed_tutorial": player_info.get("completed_tutorial", 0),
                "increasedPopulation": map_data.get("increasedPopulation", 0)
            })
    return json.dumps(players_data)

@app.route("/api/admin/items")
def admin_items():
    from get_game_config import get_game_config
    config = get_game_config()
    items_list = []
    
    # Track existing IDs to avoid duplicates
    seen_ids = set()
    
    for item in config.get("items", []):
        if item.get("name"):
            item_id = int(item.get("id"))
            seen_ids.add(item_id)
            items_list.append({
                "id": item_id,
                "name": item.get("name"),
                "type": item.get("type")
            })
            
    # Also parse custom CSV items from tools/se_unit_patch.csv dynamically
    csv_path = os.path.join(BASE_DIR, "tools", "se_unit_patch.csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    col = line.strip().split("\t")
                    if len(col) >= 3 and col[0].isdigit():
                        item_id = int(col[0])
                        item_name = col[2]
                        if item_id not in seen_ids:
                            seen_ids.add(item_id)
                            items_list.append({
                                "id": item_id,
                                "name": item_name,
                                "type": "custom"
                            })
        except Exception as e:
            print(f" [GM] Error parsing se_unit_patch.csv: {e}")
    
    # Map thumbnails dynamically
    thumbs_map = {}
    thumbs_dir = os.path.join(ASSETS_DIR, "buildingthumbs")
    if os.path.exists(thumbs_dir):
        for f in os.listdir(thumbs_dir):
            if f.endswith((".jpg", ".png")):
                parts = f.split("_", 1)
                if parts[0].isdigit():
                    thumbs_map[int(parts[0])] = f"/assets/buildingthumbs/{f}"
                    
    return {"items": items_list, "thumbs": thumbs_map}

@app.route("/api/admin/update", methods=['POST'])
def admin_update():
    from sessions import session, save_session
    data = request.json
    pid = data.get("pid")
    save = session(pid)
    if not save:
        return {"success": False, "error": "Player not found"}
    
    player_info = save["playerInfo"]
    player_info["cash"] = data.get("cash", player_info.get("cash", 0))
    
    default_map = player_info.get("default_map", 0)
    map_data = save["maps"][default_map]
    
    for field in ["coins", "xp", "level", "stone", "wood", "food"]:
        if field in data:
            map_data[field] = data[field]
            player_info[field] = data[field]
            
    if "increasedPopulation" in data:
        map_data["increasedPopulation"] = data["increasedPopulation"]
        
    if "completed_tutorial" in data:
        completed = int(data["completed_tutorial"])
        player_info["completed_tutorial"] = completed
        if completed == 1:
            # Also unlock dragon nest for a fully functional player state
            private_state = save.setdefault("privateState", {})
            private_state["dragonNestActive"] = 1
            
    if "unlock_all_quests" in data:
        if data["unlock_all_quests"] == 1:
            quest_ids = [
                100000002, 100000003, 100000006, 100000007, 100000008, 100000011,
                100000012, 100000013, 100000014, 100000015, 100000018, 100000019,
                100000020, 100000021, 100000022, 100000023, 100000028, 100000033,
                100000035, 100000036, 100000041, 100000042, 100000043, 100000044,
                100000045, 100000046, 100000047, 100000051, 100000052, 100000053,
                100000054, 100000055, 100000090, 100000091, 100000092
            ]
            map_data["questTimes"] = [[qid, 1] for qid in quest_ids]
            map_data["lastQuestTimes"] = [[qid, 1781522800] for qid in quest_ids]
            
            # Progression properties inside privateState
            private_state = save.setdefault("privateState", {})
            private_state["unlockedQuestIndex"] = 100
            
            # Unlock all survival/ship maps
            s_maps = private_state.setdefault("survivalMaps", {})
            survival_ids = [
                "100000035", "100000036", "100000037", "100000038", "100000039", 
                "100000040", "100000041", "100000042", "100000043", "100000044", 
                "100000045", "100000046", "100000047", "100000048", "100000049"
            ]
            for s_id in survival_ids:
                s_maps[s_id] = {"ts": 1781522800, "tp": 1}
        elif data["unlock_all_quests"] == -1:
            # Reset all quests
            map_data["questTimes"] = []
            map_data["lastQuestTimes"] = []
            private_state = save.setdefault("privateState", {})
            private_state["unlockedQuestIndex"] = 0
            private_state["survivalMaps"] = {}
                
    if "expansions" in data:
        map_data["expansions"] = data["expansions"]
        
    save_session(pid)
    return {"success": True}

@app.route("/api/admin/add_item", methods=['POST'])
def admin_add_item():
    from sessions import session, save_session
    data = request.json
    pid = data.get("pid")
    item_id = int(data.get("item_id"))
    quantity = int(data.get("quantity", 1))
    
    save = session(pid)
    if not save:
        return {"success": False, "error": "Player not found"}
        
    private_state = save.setdefault("privateState", {})
    gifts = private_state.setdefault("gifts", [])
    
    # Pad the gifts list if it is not long enough
    if len(gifts) <= item_id:
        gifts.extend([0] * (item_id - len(gifts) + 1))
        
    gifts[item_id] += quantity
    
    save_session(pid)
    return {"success": True}

@app.route("/api/admin/force_sync", methods=['POST'])
def admin_force_sync():
    pid = request.args.get("pid")
    if pid:
        force_sync_players.add(pid)
        print(f" [GM SYNC] Registered force sync reload request for player: {pid}")
    return {"success": True}



########
# MAIN #
########

print (" [+] Running server...")

if __name__ == '__main__':
    app.secret_key = 'SECRET_KEY'
    app.run(host=host, port=port, debug=False)
