import requests
import time
import re
import math
import base64
import hashlib

# --- REGISTRY ---
COMMAND_REGISTRY = {}

def command(name, usage="", desc=""):
    # This mainly exists to auto build the help menu :3
    def decorator(func):
        COMMAND_REGISTRY[name.lower()] = {
            "func": func,
            "usage": usage,
            "desc": desc
        }
        return func
    return decorator

# --- HELPER FUNCTIONS ---
def safe_int(value, fallback=0):
    if value is None or str(value).strip() == "":
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback
       
def is_admin(sender_player_id, bot_ctx):
    admins = bot_ctx["state"].get("admins", [])
    for admin in admins:
        if str(admin.get("player_id")) == str(sender_player_id):
            return True
    return False

def lookup_gd_user(target_name, bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/getGJUsers20.php"
    payload = {"str": target_name, "secret": bot_ctx["COMMON_SECRET"]}
    try:
        response = requests.post(url, data=payload, headers=bot_ctx["HEADERS"])
        res_text = response.text.strip()
        if res_text == "-1" or not res_text:
            return None
            
        parts = res_text.split(":")
        user_dict = {parts[i]: parts[i+1] for i in range(0, len(parts) - 1, 2)}
            
        return {
            "username": user_dict.get("1", target_name),
            "player_id": user_dict.get("2", ""),  
            "account_id": user_dict.get("16", "") 
        }
    except Exception:
        return None

def send_private_message(target_account_id, subject, body, bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/uploadGJMessage20.php"
    b64_subject = base64.urlsafe_b64encode(subject.encode('utf-8')).decode('utf-8')
    b64_body = base64.urlsafe_b64encode(bytearray(b ^ b"14251"[i % len(b"14251")] for i, b in enumerate(body.encode('utf-8')))).decode('utf-8')
    
    payload = {
        "accountID": bot_ctx["session"]["accountID"],
        "gjp2": bot_ctx["session"]["gjp2"],
        "toAccountID": str(target_account_id),
        "subject": b64_subject,
        "body": b64_body,
        "secret": bot_ctx["COMMON_SECRET"],
        "gameVersion": "22",
        "binaryVersion": "47"
    }
    
    try:
        res = requests.post(url, data=payload, headers=bot_ctx["HEADERS"]).text.strip()
        return res == "1"
    except Exception as e:
        print(f"[!] Error sending DM: {e}")
        return False

def get_level_info(target_level_id, bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/downloadGJLevel22.php"
    payload = {
        "levelID": str(target_level_id),
        "secret": bot_ctx["COMMON_SECRET"],
        "gameVersion": "22",
        "binaryVersion": "47"
    }
    try:
        res = requests.post(url, data=payload, headers=bot_ctx["HEADERS"]).text.strip()
        if res == "-1" or not res: 
            return None
        parts = res.split('#')[0].split(':')
        return {parts[i]: parts[i+1] for i in range(0, len(parts) - 1, 2)}
    except Exception as e:
        print(f"[!] Error downloading level: {e}")
        return None

def generate_chk_upload(values, salt, key):
    """Generates the seed2 CHK string. (I did use AI for this... why did rubrub make this so hard)"""
    data_string = "".join(str(v) for v in values) + salt
    sha1_hash = hashlib.sha1(data_string.encode('utf-8')).hexdigest()
    key_bytes, hash_bytes = key.encode('utf-8'), sha1_hash.encode('utf-8')
    ciphered = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(hash_bytes)])
    return base64.urlsafe_b64encode(ciphered).decode('utf-8')

def perform_level_upload(level_string, level_name, level_version, level_desc, metadata, bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/uploadGJLevel21.php"

    # This just does some wierd seed magic required to upload GD levels
    chars = 50
    if len(level_string) < chars:
        seed_str = level_string
    else:
        step = len(level_string) // chars
        seed_str = level_string[::step][:chars]
        
    chk = generate_chk_upload(values=[seed_str], salt="xI25fpAapCQg", key="41274")
    
    payload = {
        "gameVersion": "22",
        "accountID": bot_ctx["session"]["accountID"],
        "gjp2": bot_ctx["session"]["gjp2"],
        "userName": bot_ctx["GD_USERNAME"],
        "levelID": bot_ctx["level_id"],
        "levelName": level_name,
        "levelDesc": level_desc,
        "levelVersion": int(level_version),
        "levelLength": int(metadata.get("levelLength", 0)),
        "audioTrack": int(metadata.get("audioTrack", 0)),
        "auto": 0,
        "password": 0,
        "original": 0,
        "twoPlayer": int(metadata.get("twoPlayer", 0)),
        "songID": int(metadata.get("songID", 0)),
        "objects": int(metadata.get("objects", 1)),
        "coins": int(metadata.get("coins", 0)),
        "requestedStars": 0,
        "unlisted": 2,
        "ldm": 0,
        "levelString": level_string,
        "seed2": chk,
        "secret": bot_ctx["COMMON_SECRET"]
    }
    try:
        res = requests.post(url, data=payload, headers=bot_ctx["HEADERS"]).text.strip()
        return res != "-1" and res.isdigit()
    except Exception as e:
        print(f"[!] Upload exception: {e}")
        return False

def update_desc(string, bot_ctx):
    url = f"{bot_ctx['GD_API_BASE_URL']}/updateGJDesc20.php"
    b64_desc = base64.urlsafe_b64encode(string.encode('utf-8')).decode('utf-8')
    
    payload = {
        "accountID": bot_ctx["session"]["accountID"],
        "gjp2": bot_ctx["session"]["gjp2"],
        "levelID": bot_ctx["level_id"],
        "levelDesc": b64_desc,
        "secret": bot_ctx["COMMON_SECRET"],
        "gameVersion": "22",
        "binaryVersion": "47"
    }
    
    try:
        res = requests.post(url, data=payload, headers=bot_ctx["HEADERS"]).text.strip()
        return res == "1"
    except Exception as e:
        print(f"[!] Error changing the description: {e}")
        return False

def parse_duration(duration_str):
    match = re.match(r"^(\d+)(s|m|h|d|mo|y)$", duration_str.strip().lower())
    if not match: return None
    value, unit = int(match.group(1)), match.group(2)
    unit_map = {"s": 1, "m": 60, "h": 3600, "d": 86400, "mo": 30 * 86400, "y": 365 * 86400}
    return value * unit_map[unit]

def format_remaining(seconds):
    if seconds <= 0: return "0s"
    intervals = [("y", 365 * 86400), ("mo", 30 * 86400), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    parts = []
    for unit, count in intervals:
        value = int(seconds // count)
        if value > 0:
            seconds -= value * count
            parts.append(f"{value}{unit}")
    return " ".join(parts) if parts else "0s"

def execute_pending_action(action_data, bot_ctx):
    action_type = action_data.get("action")
    args = action_data.get("args", {})

    if action_type == "level_update":
        success = perform_level_upload(
            level_string=args["levelString"],
            level_name=args["levelName"],
            level_desc=args["levelDesc"],
            level_version=args["levelVersion"],
            metadata=args["metadata"],
            bot_ctx=bot_ctx
        )
        if success:
            return "Success! The level has been updated! :3"
        else:
            return "Failed! GD refused to update the level..."

    print(f"[!] Unknown action type: '{action_type}'")
    return "An error occured! Please check logs for more info..."


# --- COMMANDS ---
@command("/ping", "/ping", "Pong!")
def handle_ping(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    return "Pong :3"

@command("/about", "/about", "Displays information about the Bot.")
def handle_about(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    return f"Bot created by BlueToadMaker and hosted by {bot_ctx['BOT_OWNER']}!"

@command("/help", "/help [page|cmd] <val>", "You are now viewing the /help commands help... why....")
def handle_help(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    cmds = list(COMMAND_REGISTRY.keys())
    per_page = 10
    total_pages = math.ceil(len(cmds) / per_page)

    if len(tokens) < 2:
        return f"Run /help page <number> or /help cmd <command>. {total_pages} pages."

    sub_action = tokens[1].lower()

    if sub_action == "page":
        if len(tokens) < 3: return f"Usage: /help page <1-{total_pages}>"
        try:
            page_num = int(tokens[2])
            if 1 <= page_num <= total_pages:
                start = (page_num - 1) * per_page
                page_cmds = cmds[start:start + per_page]
                return f"Page {page_num}: {' '.join(page_cmds)}"
            return f"Error: Invalid page. Max pages: {total_pages}."
        except ValueError:
            return "Error: Page must be a number."

    elif sub_action == "cmd":
        if len(tokens) < 3: return "Usage: /help cmd <command_name>"
        target_cmd = "/" + tokens[2].lower().replace("/", "")
        if target_cmd in COMMAND_REGISTRY:
            cmd_info = COMMAND_REGISTRY[target_cmd]
            return f"{cmd_info['usage']} - {cmd_info['desc']}"
        return f"Error: Command '{target_cmd}' not found."

    return "Invalid! Use /help page <number> or /help cmd <command>"

@command("/timehelp", "/timehelp", "Displays help info on how to format time.")
def handle_timehelp(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    return "Time help: #s = secs|#m = mins|#h = hours|#d = days|#mo = months|#y = years|5m = 5 mins and 10d = 10 days"

@command("/silent", "/silent <command>", "Comments silently, for example running a command (/silent /ban RobTop)")
def handle_silent(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: 
        return "Usage: /silent <command>"
    
    inner_text = " ".join(tokens[1:])

    print(f"[!] Processed a silent command: {inner_text} | {process_command(inner_text, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username)}")
   
    target_player_id = str(sender_id)
    for line in bot_ctx.get("current_batch", []):
        if not line.strip() or ":" not in line: 
            continue
        
        parts = line.split(':', 1)[0].split('~')
        comment_data = {parts[i]: parts[i+1] for i in range(0, len(parts) - 1, 2)}
        
        c_id = comment_data.get('6', '')
        s_pid = comment_data.get('3', '')
        
        if str(s_pid) == target_player_id and c_id:
            bot_ctx["delete_comment"](c_id, bot_ctx)
            break
            
    return None

@command("/confirm", "/confirm", "Confirms an action.")
def handle_confirm(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    
    state = bot_ctx["state"]
    pending = state.get("pending_action")
    
    if not pending:
        return "Error: There's nothing pending to confirm."
        
    result_message = execute_pending_action(pending, bot_ctx)
        
    del state["pending_action"]
    
    return f"{result_message}"

@command("/cancel", "/cancel", "Cancels an action.")
def handle_cancel(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
        
    state = bot_ctx["state"]
    if "pending_action" in state:
        del state["pending_action"]
        return f"Cancelled!"
        
    return "Nothing to cancel right now!"

@command("/op", "/op <player_name>", "Grants admin privileges.")
def handle_op(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /op <player_name>"
    
    user_info = lookup_gd_user(tokens[1], bot_ctx)
    if not user_info or not user_info["player_id"]:
        return f"Error: Player '{tokens[1]}' not found."
        
    admins = bot_ctx["state"].setdefault("admins", [])
    if any(str(a.get("player_id")) == str(user_info["player_id"]) for a in admins):
        return f"{user_info['username']} is already an admin."
            
    admins.append({
        "username": user_info["username"],
        "account_id": str(user_info["account_id"]),
        "player_id": str(user_info["player_id"]),
        "role": "admin"
    })
    return f"Success: {user_info['username']} is now admin."

@command("/deop", "/deop <player_name>", "Revokes admin powers.")
def handle_deop(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /deop <player_name>"
    
    target = tokens[1].lower()
    if target == bot_ctx['BOT_OWNER']: return "Error: Cannot deop the owner."
    
    admins = bot_ctx["state"].get("admins", [])
    for admin in admins:
        if admin.get("username", "").lower() == target:
            admins.remove(admin)
            return f"Success: Removed {admin['username']} from admins."
    return f"Error: '{tokens[1]}' is not an admin."

@command("/mute", "/mute <player_name> <duration>", "Mutes a user and stops them from commenting.")
def handle_mute(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 3: return "Usage: /mute <player_name> <duration>"
    
    name, dur_str = tokens[1], tokens[2]
    seconds = parse_duration(dur_str)
    if seconds is None: return "Error: Invalid duration format. Run /timehelp for help on formatting time"
    
    user_info = lookup_gd_user(name, bot_ctx)
    if not user_info or not user_info["player_id"]: return f"Error: Player '{name}' not found."
    
    mutes = bot_ctx["state"].setdefault("mutes", {})
    now = time.time()
    mutes[str(user_info["player_id"])] = { 
        "username": user_info["username"],
        "issued_at": now,
        "expires_at": now + seconds
    }
    return f"Success: {user_info['username']} muted for {dur_str}."

@command("/unmute", "/unmute <player_name>", "Lifts a users mute.")
def handle_unmute(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /unmute <player_name>"
    
    target = tokens[1].lower()
    mutes = bot_ctx["state"].setdefault("mutes", {})
    for p_id, data in list(mutes.items()):
        if data.get("username", "").lower() == target:
            del mutes[p_id]
            return f"Success: Unmuted {data['username']}."
    return f"Error: '{tokens[1]}' is not muted."

@command("/clearcomment", "/clearcomment <player_name>", "Wipes a user comments.")
def handle_clearcomment(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /clearcomment <player_name>"
    
    user_info = lookup_gd_user(tokens[1], bot_ctx)
    if not user_info or not user_info["player_id"]: return "Error: Player not found."
    
    deleted_count = 0
    target_player_id = str(user_info["player_id"])
    
    for line in bot_ctx.get("current_batch", []):
        if not line.strip() or ":" not in line: continue
        parts = line.split(':', 1)[0].split('~')
        comment_data = {parts[i]: parts[i+1] for i in range(0, len(parts) - 1, 2)}
        
        c_id, s_pid = comment_data.get('6', ''), comment_data.get('3', '')
        if str(s_pid) == target_player_id and c_id:
            if bot_ctx["delete_comment"](c_id, bot_ctx):
                deleted_count += 1
                
    return f"Success: Deleted {deleted_count} comments from {user_info['username']}."

@command("/ban", "/ban <player_name> <duration>", "Mutes a player and clears that users comments.")
def handle_ban(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 3: return "Usage: /ban <player_name> <duration>"
    
    name, dur_str = tokens[1], tokens[2]
    seconds = parse_duration(dur_str)
    if seconds is None: return "Error: Invalid duration format. Run /timehelp for help on formatting time"
    
    user_info = lookup_gd_user(name, bot_ctx)
    if not user_info or not user_info["player_id"]: return f"Error: Player '{name}' not found."
    
    bans = bot_ctx["state"].setdefault("bans", {})
    now = time.time()
    bans[str(user_info["player_id"])] = { 
        "username": user_info["username"],
        "expires_at": now + seconds
    }
    
    return f"Success: Banned {user_info['username']} and cleared their old messages (Banned for {dur_str})."

@command("/unban", "/unban <player_name>", "Lifts a users ban.")
def handle_unban(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /unban <player_name>"
    
    target = tokens[1].lower()
    bans = bot_ctx["state"].setdefault("bans", {})
    for p_id, data in list(bans.items()):
        if data.get("username", "").lower() == target:
            del bans[p_id]
            return f"Success: Unbanned {data['username']}."
    return f"Error: '{tokens[1]}' is not banned."

@command("/mutelist", "/mutelist [username]", "Lists mute users and when they will be unmuted.")
def handle_mutelist(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    mutes = bot_ctx["state"].setdefault("mutes", {})
    now = time.time()
    if len(tokens) < 2:
        lines = []
        for p_id, data in list(mutes.items()):
            rem = data["expires_at"] - now
            if rem <= 0: del mutes[p_id]
            else: lines.append(f"{data['username']}")
        return "Muted: " + ", ".join(lines) if lines else "Mute list empty."
    else:
        target = tokens[1].lower()
        for p_id, data in list(mutes.items()):
            rem = data["expires_at"] - now
            if rem <= 0: del mutes[p_id]
            elif data.get("username", "").lower() == target:
                return f"{data['username']} is muted for {format_remaining(rem)}"
        return f"Error: '{tokens[1]}' is not muted."

@command("/banlist", "/banlist [username]", "Lists banned users and when they will be unbanned.")
def handle_banlist(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    bans = bot_ctx["state"].setdefault("bans", {})
    now = time.time()
    if len(tokens) < 2:
        lines = []
        for p_id, data in list(bans.items()):
            rem = data["expires_at"] - now
            if rem <= 0: del bans[p_id]
            else: lines.append(f"{data['username']}")
        return "Banned: " + ", ".join(lines) if lines else "Ban list empty."
    else:
        target = tokens[1].lower()
        for p_id, data in list(bans.items()):
            rem = data["expires_at"] - now
            if rem <= 0: del bans[p_id]
            elif data.get("username", "").lower() == target:
                return f"{data['username']} is banned for {format_remaining(rem)}"
        return f"Error: '{tokens[1]}' is not banned."

@command("/oplist", "/oplist", "Lists admins.") 
def handle_oplist(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    op = bot_ctx["state"].get("admins", []) 
    lines = []
    for data in op:
        username = data.get('username', 'Unknown')
        lines.append(f"{username}")
    return "Admins: " + ", ".join(lines) if lines else "OP list empty..."

@command("/updatelvl", "/updatelvl <level_id|revert>", "Updates this level or reverts to the last version.")
def handle_updatelvl(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): 
        return "Error: Unauthorized."
    if len(tokens) < 2: 
        return "Usage: /updatelvl <level_id|revert>"
    
    target = tokens[1].lower()
    state = bot_ctx["state"]
    
    # Fetch current chatroom details
    current_room = get_level_info(bot_ctx["level_id"], bot_ctx)
    if not current_room:
        return "Error: Could not fetch the current chatroom's level data from the server!"
        
    chatroom_name = current_room.get('2')
    chatroom_desc = current_room.get('3')
    next_version = int(current_room.get('5', '1')) + 1

    if target == "revert":
        if "backup_level" not in state:
            return "Error: No backup level found to revert to!"
            
        # Set the action as pending
        state["pending_action"] = {
            "action": "level_update",
            "args": {
                "levelString": state["backup_level"]["levelString"],
                "levelName": chatroom_name,
                "levelDesc": chatroom_desc,
                "levelVersion": next_version,
                "metadata": state["backup_level"]["metadata"]
            }
        }
        return f"Loaded last version! (V{next_version-2}) /confirm to revert or /cancel."
        
    # Download target level
    target_lvl = get_level_info(target, bot_ctx)
    if not target_lvl or '4' not in target_lvl:
        return f"Error: Could not fetch level {target}. Does the level exist?"
        
    target_name = target_lvl.get('2', 'Unknown')
    
    metadata_pack = {
        "desc": target_lvl.get('3', ''),
        "levelLength": target_lvl.get('15', '0'),
        "audioTrack": target_lvl.get('12', '0'),
        "auto": target_lvl.get('25', '0'),
        "password": target_lvl.get('27', '0'),
        "original": target_lvl.get('30', '0'),
        "twoPlayer": target_lvl.get('31', '0'),
        "songID": target_lvl.get('35', '0'),
        "objects": target_lvl.get('45', '1'),
        "coins": target_lvl.get('37', '0'),
        "requestedStars": target_lvl.get('39', '0')
    }
    
    # Create a backup of the level to revert to
    state["backup_level"] = {
        "levelString": current_room.get('4', ''),
        "metadata": {
            "desc": current_room.get('3', ''),
            "levelLength": current_room.get('15', '0'),
            "audioTrack": current_room.get('12', '0'),
            "auto": current_room.get('25', '0'),
            "password": current_room.get('27', '0'),
            "original": current_room.get('30', '0'),
            "twoPlayer": current_room.get('31', '0'),
            "songID": current_room.get('35', '0'),
            "objects": current_room.get('45', '1'),
            "coins": current_room.get('37', '0'),
            "requestedStars": current_room.get('39', '0')
        }
    }

    # Set the action as pending
    state["pending_action"] = {
        "action": "level_update",
        "args": {
            "levelString": target_lvl.get('4', ''),
            "levelName": chatroom_name,
            "levelDesc": chatroom_desc,
            "levelVersion": next_version,
            "metadata": metadata_pack
        }
    }
    
    return f"Loaded level! ({target_name}) /confirm to update the level, or /cancel."

@command("/updatedesc", "/updatedesc <string>", "Changes the levels description.") 
def handle_updatedesc(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /updatedesc <string>"
    inner_text = " ".join(tokens[1:])
    success = update_desc(inner_text, bot_ctx)
    if success:
        return "Updated the level's description :3"
    else:
        return "Failed to set the levels description!"

@command("/login", "/login", "DM's you this account's login creds.") 
def handle_login(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    target_account_id = user_data.get('16', '')
    msg_subject = "Bot Credentials"
    msg_body = f"Username: {bot_ctx["GD_USERNAME"]} | Password: {bot_ctx["GD_PASSWORD"]}\nMess with the account, idc as long as you don't get it banned :P"
    success = send_private_message(target_account_id, msg_subject, msg_body, bot_ctx)    
    if success:
        return f"Check your DM's {sender_username} :3"
    else:
        return "Failed! Are your DM's public?"

@command("/dislikedelete", "/dislikedelete <amount>", "Sets the dislike threshold before a comment is auto-deleted (0 to disable).")
def handle_dislikedelete(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: 
        current = bot_ctx["state"].get("dislike_threshold", 0)
        return f"Usage: /dislikedelete <amount> (Current: {current})"
    
    try:
        amount = int(tokens[1])
        if amount < 0:
            return "Error: This is a negitives number.. no negitives pls :3 Use 0 to disable."
        bot_ctx["state"]["dislike_threshold"] = amount
        if amount == 0:
            return "Success: Dislike auto deletion has been disabled."
        return f"Success: Comments reaching {amount} disllikes will now be automatically deleted."
    except ValueError:
        return "Error: That isn't a valid number!"

@command("/delete", "/delete <comment_id>", "Removes a comment by its ID.")
def handle_delete(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."
    if len(tokens) < 2: return "Usage: /delete <comment_id>"
    
    comment_id = tokens[1]
    if bot_ctx["delete_comment"](comment_id, bot_ctx):
        return f"Success: Comment {comment_id} deleted."
    return "Error: Deletion failed."

# --- PROCESSOR EXPORT ---
def process_command(full_text, bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username):
    tokens = full_text.strip().split()
    if not tokens: return None
    
    base_command = tokens[0].lower()
    if base_command in COMMAND_REGISTRY:
        return COMMAND_REGISTRY[base_command]["func"](tokens, bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username)
    return None