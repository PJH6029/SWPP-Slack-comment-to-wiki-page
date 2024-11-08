import datetime
import json

def get_date_from_comment(comment):
    if json_data := comment.get("json_data"):
        if date := json_data.get("date"):
            date_str = datetime.datetime.strptime(date, "%y/%m/%d").strftime("%y%m%d")
            return date_str
    return comment['comment_datetime'].strftime("%y%m%d")

def _get_id_name(user_id):
    try:
        with open("id_name.json", "r", encoding="utf-8") as f:
            id_name = json.load(f)
    except FileNotFoundError:
        id_name = {}
    return id_name.get(user_id, {})

def get_team_initials(user_id):
    return _get_id_name(user_id).get("initials", user_id)

def get_team_name(user_id):
    return _get_id_name(user_id).get("name", user_id)