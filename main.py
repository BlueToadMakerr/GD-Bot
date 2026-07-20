import hashlib
import time
import uuid
import requests
import base64
import json
import os
import commands
import comment_processing
import traceback
import random
import re
from dotenv import load_dotenv

load_dotenv()

# --- BOT SETTINGS ---
GD_API_BASE_URL = "https://www.boomlings.com/database"
LOGIN_SECRET = "Wmfv3899gc9"
COMMON_SECRET = "Wmfd2893gb7"

LEVEL_ID = os.getenv("LEVEL_ID")
GD_USERNAME = os.getenv("GD_USERNAME")
GD_PASSWORD = os.getenv("GD_PASSWORD")
DVS = "10"

OWNER_USERNAME = os.getenv("OWNER_USERNAME")
OWNER_PLAYER_ID = os.getenv("OWNER_PLAYER_ID")

# --- VERBOSE LOGGING ---
VERBOSE_LOGS = True

# --- CONFIG FILE ---
STATE_FILE = "bot_config.json"

# --- RATE LIMIT SETTINGS ---
ACTIVE_INTERVAL = 3 # How long to wait before refreshing when active
COOLDOWN_INTERVAL = 60 # How long to wait before refreshing when not active
ACTIVE_DURATION = 180 # How long there should be no activity for before going inactive

HEADERS = {
    "User-Agent": "",
    "Content-Type": "application/x-www-form-urlencoded"
}

session = {
    "accountID": None,
    "uuid": None,
    "udid": None,
    "gjp2": None
}

def vlog(message):
    if VERBOSE_LOGS:
        print(f"[VERBOSE] {message}")

# --- LOADING AND SAVING ---
def load_bot_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                state["processed_ids"] = state.get("processed_ids", [])[-500:]
                state.setdefault("response_queue", [])
                state.setdefault("dislike_threshold", 0)
                state.setdefault("admins", [
                    {"username": f"{OWNER_USERNAME}", "player_id": f"{OWNER_PLAYER_ID}", "role": "owner"}
                ])
                return state
        except Exception as e:
            print(f"[-] Failed to load state file: {e}. Starting fresh...")
            
    return {
        "processed_ids": [],
        "response_queue": [],
        "admins": [{"username": f"{OWNER_USERNAME}", "player_id": f"{OWNER_PLAYER_ID}", "role": "owner"}]
    }

def save_bot_state(state):
    try:
        state_to_save = state.copy()
        state_to_save["processed_ids"] = state_to_save["processed_ids"][-500:]
        with open(STATE_FILE, "w") as f:
            json.dump(state_to_save, f, indent=4)
    except Exception as e:
        print(f"[-] Failed to save state to file: {e}")

# --- MORE FUNCTIONS ---
def generate_gjp2(password):
    return hashlib.sha1((password + "mI29fmAnxgTs").encode('utf-8')).hexdigest()

def generate_gd_udid():
    return str(uuid.uuid4())

def generate_chk(values, salt, key):
    data_string = "".join(str(v) for v in values) + salt
    sha1_hash = hashlib.sha1(data_string.encode('utf-8')).hexdigest()
    key_bytes, hash_bytes = key.encode('utf-8'), sha1_hash.encode('utf-8')
    ciphered = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(hash_bytes)])
    return base64.urlsafe_b64encode(ciphered).decode('utf-8')

def parse_gd_string(gd_str: str) -> dict:
    if not gd_str:
        return {}
    parts = gd_str.split('~')
    result = {}
    for i in range(0, len(parts) - 1, 2):
        if i + 1 < len(parts):
            result[parts[i]] = parts[i+1]
    return result

def decode_gd_base64(encoded_str: str) -> str:
    try:
        normalized = encoded_str.replace('-', '+').replace('_', '/')
        padded = normalized + '=' * (-len(normalized) % 4)
        return base64.b64decode(padded).decode('utf-8', errors='ignore').strip()
    except Exception:
        return ""

def login_to_gd():
    print("Attempting to log into Geometry Dash...")
    url = f"{GD_API_BASE_URL}/accounts/loginGJAccount.php"
    gjp2_hash = generate_gjp2(GD_PASSWORD)
    udid = generate_gd_udid()
    
    payload = {
        "userName": GD_USERNAME,
        "gjp2": gjp2_hash, 
        "secret": LOGIN_SECRET,
        "udid": udid
    }
    
    try:
        response = requests.post(url, data=payload, headers=HEADERS)
        res_text = response.text.strip()
        
        if res_text == "-1" or not res_text or response.status_code != 200:
            print(f"Login failed! Server returned: {res_text}")
            return False
        
        parts = res_text.split(",")
        if len(parts) >= 2:
            session["accountID"] = parts[0]
            session["uuid"] = parts[1]  
            session["udid"] = udid
            session["gjp2"] = gjp2_hash
            print(f"Successfully logged in! AccountID: {session['accountID']} :3\n")
            return True
        return False
    except Exception as e:
        print(f"Network error during login: {e}")
        return False

def check_gd_errors(res_text, bot_ctx):
    res_lower = res_text.lower()
    
    if "error 1020" in res_lower:
        if not bot_ctx.get("is_rate_limited"):
            print("[-] We are being rate limited by Cloudflare! Bot is going inactive...")
            bot_ctx["is_rate_limited"] = True
        return "1020"

    # If the response isn't a 1020 and we were rate limited before, let the user know!
    if bot_ctx.get("is_rate_limited"):
        print("[+] A request went through! We are no longer rate limited!!! :3")
        bot_ctx["is_rate_limited"] = False

    # These are comment bans
    if res_text == "-10":
        print("[-] Account is comment banned by RobTop! No comments from the bot will post. (Tell the chatroom!)")
        bot_ctx["comment_banned_forever"] = True
        return "banned"

    if res_text.startswith("temp_"):
        # Format should be temp_{time}_{reason} ({player_id})
        match = re.match(r"^temp_(\d+)_(.*?)(?:\s+\((\d+)\))?$", res_text)
        if match:
            ban_time, reason, pid = match.groups()
            reason = reason.strip()
            
            # 1. Are we perma banned?
            is_perma = (ban_time == "3020399")
            
            # 2. Who was banned? IP or Account
            our_uuid = str(bot_ctx["session"]["uuid"])
            is_ip_ban = bool(pid and pid != our_uuid)
            
            # 3. Build the log message
            ban_length_str = "permanently banned" if is_perma else f"banned for {ban_time}s"
            target_str = "IP" if is_ip_ban else "Account"
            
            log_msg = f"[-] {target_str} is {ban_length_str} from commenting! (Reason: '{reason}')"
            if is_ip_ban:
                log_msg += f" Caused by Player ID: {pid} (Our ID: {our_uuid})."
                
            print(log_msg)
            
            # 4. Update the bot's state
            if is_perma:
                bot_ctx["comment_banned_forever"] = True
            else:
                bot_ctx["comment_banned_until"] = time.time() + int(ban_time)
                
        else:
            print(f"[-] We were banned.. but dont know why... (Server returned: {res_text}) Comment sleeping for 5 mins..")
            bot_ctx["state"]["comment_banned_until"] = time.time() + 300 # 5 min timeout!
            
        return "banned"
        
    return "ok"

def upload_comment(text, bot_ctx):
    if bot_ctx["comment_banned_forever"]:
        return True # Fail silently...
    if bot_ctx["state"].get("comment_banned_until", 0) > time.time():
        return True
    
    url = f"{GD_API_BASE_URL}/uploadGJComment21.php"
    b64_comment = base64.urlsafe_b64encode(text.encode('utf-8')).decode('utf-8')
    target_level_id = LEVEL_ID
    
    chk_values = [GD_USERNAME, b64_comment, target_level_id, 0, 0]
    generated_chk = generate_chk(values=chk_values, salt="xPT6iUrtws0J", key="29481")

    payload = {
        "accountID": session["accountID"],
        "gjp2": session["gjp2"],
        "userName": GD_USERNAME,
        "comment": b64_comment,
        "secret": COMMON_SECRET,
        "levelID": target_level_id,
        "chk": generated_chk,
        "percent": 0,
        "gameVersion": "22",
        "binaryVersion": "47",
        "uuid": session["uuid"],
        "udid": session["udid"],
        "dvs": DVS
    }
    
    try:
        vlog(f"Uploading comment: {text}")
        res = requests.post(url, data=payload, headers=HEADERS).text.strip()
        vlog(f"Upload response: {res}")
        err_status = check_gd_errors(res, bot_ctx)
        if err_status == "1020":
            return False
        elif err_status == "banned":
            print(f"[-] Currently comment banned!")
            return True # We pretend it works so it doesnt keep retrying in the queue
        if res == "-1":
            return False
        if res.isdigit() and int(res) > 0:
            return True
        return False
    except Exception as e:
        print(f"[-] Error uploading comment: {e}")
        return False

def delete_comment(comment_id, bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/deleteGJComment20.php"
    payload = {
        "secret": bot_ctx["COMMON_SECRET"],
        "accountID": bot_ctx["session"]["accountID"],
        "gjp2": bot_ctx["session"]["gjp2"],
        "commentID": comment_id,
        "levelID": LEVEL_ID
    }
    try:
        vlog(f"Deleting comment {comment_id}...")
        return requests.post(url, data=payload, headers=bot_ctx["HEADERS"]).text.strip() == "1"
    except Exception as e:
        print(f"[-] Error deleting comment {comment_id}: {e}")
        return False

def check_and_handle_commands(bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/getGJComments21.php"
    
    payload = {
        "levelID": LEVEL_ID,
        "page": "0",
        "secret": bot_ctx["COMMON_SECRET"],
        "mode": "0",        
        "count": "100",
        "gameVersion": "22",
        "binaryVersion": "47",
        "uuid": bot_ctx["session"]["uuid"],
        "udid": bot_ctx["session"]["udid"],
        "dvs": bot_ctx["DVS"],
        "accountID": bot_ctx["session"]["accountID"],
        "gjp2": bot_ctx["session"]["gjp2"]
    }
    
    try:
        vlog(f"Fetching comments for Level ID: {LEVEL_ID}...")
        response = requests.post(url, data=payload, headers=bot_ctx["HEADERS"])
        res_text = response.text.strip().split('#')[0]
        
        if check_gd_errors(res_text, bot_ctx) != "ok":
            return False, False
        if not res_text:
            vlog(f"No comments returned...")
            return False, False
            
        comment_lines = res_text.split('|')
        bot_ctx["current_batch"] = list(comment_lines)
        comment_lines.reverse()
        
        command_detected, new_comments_detected = False, False
        processed_ids = bot_ctx["state"]["processed_ids"]
        now = time.time()
        
        for line in comment_lines:
            if not line.strip() or ":" not in line: continue
                
            parts_split = line.split(':', 1)
            comment_part = parts_split[0]
            user_part = parts_split[1] if len(parts_split) > 1 else ""
            
            comment_data = parse_gd_string(comment_part)
            user_data = parse_gd_string(user_part) if user_part else {}

            # Info on who sent the comment
            comment_id = comment_data.get('6', '')
            sender_player_id = comment_data.get('3', '')
            sender_username = user_data.get('1', '')

            # Skip if comment data is invalid
            if not sender_player_id or not comment_id: continue
            if sender_player_id == bot_ctx["session"]["uuid"]: continue

            if comment_processing.old_comments(bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username): continue

            # Check if already processed
            is_processed = False
            for item in processed_ids:
                if isinstance(item, dict) and item.get("id") == comment_id:
                    is_processed = True
                    break
                elif item == comment_id: # Fallback :3
                    is_processed = True
                    break
                    
            if is_processed: continue

            # New comments!
            new_comments_detected = True

            if comment_processing.new_comments(bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username): continue

            decoded_body = decode_gd_base64(comment_data.get('2', ''))
            print(f"[+] New comment detected (ID: {comment_id}, Sender: {sender_player_id}, User: {sender_username}): {decoded_body}")

            command_output = commands.process_command(decoded_body, bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username)
 
            if command_output is not None:
                print(f"[!] Command triggered. Queueing: '{command_output}'")
                bot_ctx["state"]["response_queue"].append(command_output)
                command_detected = True

            # Save comment details and user info
            processed_ids.append({
                "id": comment_id, 
                "text": decoded_body,
                "player_id": sender_player_id,
                "username": sender_username
            })

            if len(processed_ids) > 500:
                processed_ids.pop(0)
                
        vlog("Saving config...")
        save_bot_state(bot_ctx["state"])
                
        return command_detected, new_comments_detected
    except Exception as e:
        stack_trace_string = traceback.format_exc()
        if VERBOSE_LOGS:
            print(f"[-] Error checking level comments:\n{stack_trace_string}")
        else:
            print(f"[-] Error checking level comments: {e}")
        return False, False

def handle_outbound_queue(bot_ctx, current_time, last_upload_time):
    queue = bot_ctx["state"]["response_queue"]
    if not queue: return last_upload_time
        
    cooldown_remaining = 15 - (current_time - last_upload_time)
    if cooldown_remaining > 0:
        vlog(f"Outbound queue has {len(queue)} items, but upload cooldown active ({int(cooldown_remaining)}s left).")
        return last_upload_time
        
    vlog("Processing next item in outbound queue...")
    if upload_comment(queue[0], bot_ctx):
        queue.pop(0)
        save_bot_state(bot_ctx["state"])
        return current_time
        
    vlog("Upload failed, keeping in queue.")
    return current_time

def main():
    if not login_to_gd(): return

    bot_ctx = {
        "GD_API_BASE_URL": GD_API_BASE_URL,
        "COMMON_SECRET": COMMON_SECRET,
        "HEADERS": HEADERS,
        "session": session,
        "DVS": DVS,
        "state": load_bot_state(),
        "delete_comment": delete_comment,
        "vlog": vlog,
        "is_rate_limited": False,
        "comment_banned_forever": False,
        "level_id": LEVEL_ID,
        "GD_USERNAME": GD_USERNAME,
        "GD_PASSWORD": GD_PASSWORD,
        "BOT_OWNER": OWNER_USERNAME,
        "current_batch": []
    }
    
    print(f"Bot Is Online! Verbose mode is {'ON' if VERBOSE_LOGS else 'OFF'}.")
    last_activity_time, last_upload_time = 0, 0
    
    while True:
        current_time = time.time()
        found_cmd, found_new = check_and_handle_commands(bot_ctx)
        last_upload_time = handle_outbound_queue(bot_ctx, current_time, last_upload_time)
        
        is_active = (current_time - last_activity_time) <= ACTIVE_DURATION or len(bot_ctx["state"]["response_queue"]) > 0
        if bot_ctx.get("is_rate_limited"):
            is_active = False
        
        if found_cmd or found_new:
            last_activity_time = time.time()
            sleep_time = ACTIVE_INTERVAL
        else:
            sleep_time = ACTIVE_INTERVAL if is_active else COOLDOWN_INTERVAL
            
        vlog(f"Loop complete! Sleeping for {sleep_time} seconds... (Currently {'active' if is_active else 'not active'})\n")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()