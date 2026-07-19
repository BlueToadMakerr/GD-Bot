import random
import time

# --- HELPER FUNCTIONS ---
def enforce_deletion(c_id, log_message, bot_ctx):
   print(f"[!] {log_message}")
   bot_ctx["delete_comment"](c_id, bot_ctx)

# Comment Processing
def old_comments(bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username):
    now = time.time()
    # Check if the user is banned
    bans = bot_ctx["state"].setdefault("bans", {})
    if sender_player_id in bans:
        if now < bans[sender_player_id]["expires_at"]:
            enforce_deletion(comment_id, f"Player {sender_player_id} is banned. Deleting comment {comment_id}...", bot_ctx)
            return True # Returning true will tell the main script to skip everything else
        else:
            bot_ctx["vlog"](f"Ban expired for Player ID {sender_player_id}. Removing...")
            del bans[sender_player_id]
           
    # Dislike delete
    dislike_threshold = bot_ctx["state"].get("dislike_threshold", 0)
    if dislike_threshold > 0:
        comment_likes = int(comment_data.get('4', 0))
        if comment_likes <= -dislike_threshold:
            enforce_deletion(comment_id, f"Comment {comment_id} reached dislike threshold. Deleting...", bot_ctx)
            return True

def new_comments(bot_ctx, comment_data, user_data, comment_id, sender_player_id, sender_username):
    now = time.time()

    # Check if the user is muted
    mutes = bot_ctx["state"].setdefault("mutes", {})
    if sender_player_id in mutes:
        if now < mutes[sender_player_id]["expires_at"]:
            enforce_deletion(comment_id, f"Player {sender_player_id} is muted. Deleting comment {comment_id}...", bot_ctx)
            return True
        else:
            bot_ctx["vlog"](f"Mute expired for Player ID {sender_player_id}. Removing...")
            del mutes[sender_player_id]

    # Random events!
    rng = random.randint(1, 1000)
    if rng == 1000:
        random_str = f"{sender_username} is a cutie! >w<"
        print(f"[!] Random event triggered! Queueing: '{random_str}'")
        bot_ctx["state"]["response_queue"].append(random_str)