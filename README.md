# GD-Bot
Ever wanted to moderate your Geometry Dash chat rooms? No? Well too bad!

This python script will allow you to create a bot and have it listen for commands!

You can ban people, delete comments, create random events, moderate users, and so much more!


## Installing
### Installing python

You would need Python 3.8+ to run this. uhh.. you probably already have this.. if not.. google how to install it idk :3

### Installing dependincies
There are only 2 depencencies you need to install, requests and python-dotenv
```bash
pip install requests python-dotenv
```

### The GD Bot account itself

A dedicated Geometry Dash Account: I highly recommend to use an alternative account for your bot!

A target Geometry Dash Level ID: An uploaded level by the bot (or whatever account you run this off) that will serve as the bot's dedicated chatroom!

### Creating and configuring Environment Variables

Use the `.env.example` file and rename it to `.env`. Also make sure you replace all of the values with your info ^w^

.env.example
```env
# GD Account Credentials
GD_USERNAME=bot_username
GD_PASSWORD=bot_password

# Configuration
LEVEL_ID=level_created_from_the_bots_account

# Owner Settings
OWNER_USERNAME=your_username
OWNER_PLAYER_ID=your_player_id
```

### Run the Bot
It will now listen for comments and run commands!
```bash
python main.py
```

---

## Built in commands!

Admins can trigger commands inside the level's comment section by using a forward slash (`/`). Non-admin users only have access to public commands.

### Public Commands

| Command | Usage | Description |
| --- | --- | --- |
| `/ping` | `/ping` | Returns `Pong :3` |
| `/about` | `/about` | Displays who made the mod, and who is hosting it! |
| `/help` | `/help [page\|cmd] <val>` | The help menu. :3 |
| `/timehelp` | `/timehelp` | Explains how format time! |
| `/mutelist` | `/mutelist [username]` | Lists currently muted players and their remaining duration. |
| `/banlist` | `/banlist [username]` | Lists currently banned players and their remaining duration. |
| `/oplist` | `/oplist` | Lists all op'd players |
| `/repeat` | `/repeat <amount>` | How many times something is repeated for the bot to join. |

### Administrative Commands

Commands only admins can use!

| Command | Usage | Description |
| --- | --- | --- |
| `/silent` | `/silent <command>` | Executes commands silently |
| `/op` | `/op <player_name>` | Gives a user admin. |
| `/deop` | `/deop <player_name>` | Takes a user admin role away. (Note: The owner can not be deop'd) |
| `/mute` | `/mute <player_name> <duration>` | Mutes a user for a duration. All new comments from that player will be instantly deleted until their mute is up. |
| `/unmute` | `/unmute <player_name>` | Removes that players mute. |
| `/ban` | `/ban <player_name> <duration>` | Bans a player for a duration. **All** comments from that player will be deleted when they are banned. |
| `/unban` | `/unban <player_name>` | Removes that players ban |
| `/clearcomment` | `/clearcomment <player_name>` | Deletes all comments from that player. |
| `/delete` | `/delete <comment_id>` | Deletes an explicit comment by its comment ID. |
| `/dislikedelete` | `/dislikedelete <amount>` | A setting telling how many dislikes a comment needs to auto-delete. Use `0` to disable. |
| `/updatedesc` | `/updatedesc <string>` | Edits and updates the chatroom's description. |
| `/updatelvl` | `/updatelvl <level_id\|revert>` | Clones the given level to the current level. |
| `/confirm` | `/confirm` | Confirms a command (currently just `/updatelvl`) |
| `/cancel` | `/cancel` | Cancels a command (currently just `/updatelvl`) |
| `/login` | `/login` | DMs the bots credentals to the admin running the command. |

> **Note:** The `/login` command will give the bots Username and Password to the admin asking for them. If you find this to not be needed, then delete this command, otherwise make sure you dont accedentallty op someone and get the bots credentals exposed :3

---

## Adding to the bot

Adding new stuff to the bot can be done through `commands.py` and `comment_processing.py`

### Creating a new command

To create a new command, open `commands.py` and add the `@command` decorator above your function:

```python
@command(
    name="/mycommand", 
    usage="/mycommand <arg1>", 
    desc="Explain what your command does here."
)
def handle_mycommand(tokens, bot_ctx, comment_data, user_data, comment_id, sender_id, sender_username):
    # 1. (Optional) Make the command only available for admins
    if not is_admin(sender_id, bot_ctx): return "Error: Unauthorized."

    # 2. Parse arguments using the token array
    if len(tokens) < 2:
        return "Usage: /mycommand <arg1>"
        
    user_argument = tokens[1]

    # Run your code here, and then return

    # The returned value is what the bot will comment and the user will see. If you don't want the bot to return anything, then return with None
    return f"{sender_username} ran the command with the argument: {user_argument}"

```

### Proccessing comments

To proccess comments, open `comment_processing.py` and add code to either `old_comments()` or `new_comments()`. Use the perameters (See below) to see who sent that comment.

#### Old/Existing Comments (`old_comments`)
This processes all comments (up to 100 recent comments). Currently this does the following, but you can add more functions!

Ban Enforcement: Deletes the users comments if they are banned

Dislike deleting: If the configured dislike threshold is active (dislike_threshold > 0), any comment that has that many dislikes will be deleted.

#### New Comments (`new_comments`)
This runs code on only newly indexed comments. Currently this does the following, but you can add more functions!

Mute Enforcement: If a new comment is detected from a muted player, that players comments will be deleted

Repeats: If a new comment is repeated x amount of times (repeat_comment), The bot will also repeat it and join in!

Random Events: New comments have a 1 in 1000 chance of triggering an "event". When triggered, a message `"[Username] is a cutie! >w<"` is posted to the level chat.

---

### More info about the perameters:

* `tokens`: Arguments the user used. For example `["/mute", "RobTop", "1d"]`.
* `bot_ctx`: A lot more data about the bot itself, can be used to get the bots username and password, owner, state, and run functions like `bot_ctx["delete_comment"]()`. Look inside main.py for more info.
* `comment_data` & `user_data`: The data about the comment and user themselves. Like the account id of the user running it, or their icon.
* `sender_id` & `sender_username`: Premade vars containing the users ID and username.

---

## License

The code is distributed as open-source under the **MIT License**. Check the `LICENSE` file for more info :3