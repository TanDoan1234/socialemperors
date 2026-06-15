import json

from database import db_load_quest

def get_quest_map(questid):
    try:
        qid = int(questid)
        d = db_load_quest(qid)
        if not d:
            return("", 404)
        return(d, 200)
    except Exception as e:
        print(f" * Error loading quest {questid} from SQLite: {e}")
        return("", 500)
