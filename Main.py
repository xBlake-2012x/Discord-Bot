import os
import traceback
import discord
from discord.ext import commands
import requests
import asyncio
from datetime import datetime, timedelta, timezone
import mimetypes
import google.generativeai as genai
import json
from discord.ui import Button
import aiohttp
from discord.ext import tasks
import random
import re
import time
import math
from discord import ui
from Storage.suffix import suffix_number
from google.api_core import exceptions
from discord.ui import View, Select, Modal, TextInput
# Set this to true to stop users using commands
locked = False

genai.configure(api_key="API_Key")

model = genai.GenerativeModel("models/gemini-2.5-flash")

default_settings = {
    "roast_toggle": True,
    "compliment_toggle": True,
    "roast/compliment profanity": True,
    "roast intensity": "10",
    "compliment intensity": "10"
}

founder_id = 1406075868786196591

curse_words = [
    # F-word variants
    "fuck", "fuc", "fck", "fk", "wtf", "stfu", "sybau",
    "fukin", "fkn", "fking", "fuk", "fux", "fukk", "fooker",
    "fudge", "fudging", "effin", "effing", "omfg", "idfk", "idfc",
    "motherfucker", "mf", "mofo", "fml",

    # S-word variants
    "shit", "sht", "sh", "ts", "tf", "sh1t", "shi", "shiz", "shite", "bullshit", "bullsh",
    "horseshit", "ape shit", "batshit", "dipshit",

    # B-word variants
    "bitch", "btch", "bich", "biatch", "betch", "beetch", "bishes", "bish",

    # A-word variants
    "ass", "asses", "arse", "asshole", "ahole", "ashole", "a-hole", "jackass",
    "dumbass", "smartass", "badass", "lameass",

    # D-word variants
    "damn", "dam", "dmn", "dammit", "damnit", "goddamn", "gdamn",

    # Sexual / vulgar
    "dick", "d1ck", "diks", "dix", "prick", "cock", "c0ck", "cok", "titties", "titty",
    "boob", "boobs", "booby", "balls", "nuts", "bollocks", "willy", "dong",

    # Insults / harsh slang
    "bastard", "bstrd", "jerk", "idiot", "moron", "loser", "douche", "douchebag",
    "scumbag", "clanker", "piss", "pissed", "pissing",

    # Others
    "crap", "crp", "bs", "bullcrap",
    "slut", "whore", "hoe", "skank", "thot",
    "wanker", "tosser", "twat",
    "dyke", "dyk", "queer" , "retard", "r3tard", 'AF', 'af'
]


muteable_words = ['nig','nigger','nigg','nigga','niga']

full_curse_words = [word for word in curse_words if len(word) >= 4]
short_fragments = [word for word in curse_words if len(word) < 4]

pplcurseamt = {}
with open('pplcurse.json','r') as f:
    pplcurseamt = json.load(f)

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

#channels
APPLICATION_CHANNEL_ID = 1419813007424229476

def safe_int(string):
    try:
        return int(string)
    except:
        return None

with open('Number','r') as f:
    number = safe_int(f.read())
if number is None:
    number = 0
with open('lastcounter','r') as f:
    countedlast = f.read()

@tasks.loop(seconds=60)
async def cleanup_expired_punishments(file_path="punishments.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return False  # No file to clean

    updated_data = {}
    now = datetime.now()

    for user_id, punishments in data.items():
        active = []
        for p in punishments:
            if p["expires"] is None:
                active.append(p)
            else:
                try:
                    expiry = datetime.fromisoformat(p["expires"])
                    if expiry > now:
                        active.append(p)
                except ValueError:
                    # If the date format is invalid, keep it (or log it)
                    active.append(p)

        if active:
            updated_data[user_id] = active

    # Save cleaned data
    with open(file_path, "w") as f:
        json.dump(updated_data, f, indent=4)

    return True


@tasks.loop(seconds=5)
async def update_settings():
    directory = "settings/"
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            filepath = os.path.join(directory, filename)
            with open(filepath, "r") as f:
                data = json.load(f)

            for _ in default_settings:
                if not _ in data:
                    data[_] = default_settings[_]

            # 💾 Save it back
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)

async def startup_cleanup_and_delete():
    # List of channel IDs you need to check
    target_channel_ids = [1419817842961813708]

    for channel_id in target_channel_ids:
        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        # Fetch the last message (limit=1)
        try:
            # We use history with limit=1 to get the last message efficiently
            messages = [msg async for msg in channel.history(limit=1)]

            if messages:
                last_msg = messages[0]

                # Check if the last message was sent by this bot
                if last_msg.author == bot.user:
                    # If the last message was the bot's, delete it
                    await last_msg.delete()

        except Exception as e:
            # Handle permissions errors or network issues gracefully
            print(f"Error processing channel {channel_id}: {e}")

class MockMessage:
    """A minimal object to satisfy ctx.message.delete()."""

    def __init__(self):
        # The delete method needs to be an awaitable function
        async def mock_delete():
            print("Mock message deleted successfully.")
            pass

        self.delete = mock_delete

class MockContext:
    """The final, complete context object for a command."""

    def __init__(self, bot, channel, member):
        self.bot = bot
        self.channel = channel
        self.guild = channel.guild
        self.message = MockMessage()
        self.author = member

        # --- CRITICAL ADDITION: The send method ---

    async def send(self, *args, **kwargs):
        """Emulates ctx.send() by forwarding the call to the channel object."""
        return await self.channel.send(*args, **kwargs)

    # ------------------------------------------

    # Other necessary properties
    @property
    def me(self):
        return self.guild.me

countedlast = safe_int(countedlast)
guild = bot.get_guild(1411439308778246297)
POLL_ROLE = None
@bot.event
async def on_ready():
    global POLL_ROLE
    guild = bot.get_guild(1411439308778246297)
    POLL_ROLE = guild.get_role(1433236813237194792)
    print(f"{bot.user} has entered the shrine.")
    channel = bot.get_channel(1413971808411193455)
    await channel.send(f'The bot have started, and the starting number is {number}')
    await startup_cleanup_and_delete()
    r9 = {}
    pl = {}
    cs = {}
    jb = {}
    jbs = {}
    with open("hate_speech.json") as f:
        r9 = json.load(f)
    with open("punishment_logs.json") as f:
        pl = json.load(f)
    with open("Coins.json") as f:
        cs = json.load(f)
    with open("Jobs.json") as f:
        jb = json.load(f)
    with open("JobWork.json") as f:
        jbs = json.load(f)
    jbu = jb["Users"]

    for member in guild.members:
        if not member.bot:
            if not str(member.id) in r9:
                r9[str(member.id)] = 0
            if not str(member.id) in cs:
                cs[str(member.id)] = 0
            if not str(member.id) in pl:
                pl[str(member.id)] = {}
            if not str(member.id) in jbu:
                jbu[str(member.id)] = None
            if not str(member.id) in jbs["time"]:
                jbs["time"][str(member.id)] = 0
            if not str(member.id) in jbs["amount"]:
                jbs["amount"][str(member.id)] = 0
    jb["Users"] = jbu

    with open("hate_speech.json",'w') as f:
        json.dump(r9, f, indent=4)
    with open("punishment_logs.json",'w') as f:
        json.dump(pl, f, indent=4)
    with open("Coins.json",'w') as f:
        json.dump(cs, f, indent=4)
    with open("Jobs.json",'w') as f:
        json.dump(jb, f, indent=4)
    with open("JobWork.json",'w') as f:
        json.dump(jbs, f, indent=4)

    application_channel = bot.get_channel(1419817842961813708)
    bot_member = application_channel.guild.get_member(bot.user.id)
    mock_ctx = MockContext(bot, application_channel, bot_member)
    await application_panel(mock_ctx)

    update_settings.start()
    cleanup_expired_punishments.start()
    income_players.start()

@bot.command()
async def help(ctx):
    role_id = 1412976484322246787
    if any(role.id == role_id for role in ctx.author.roles):
        mod = await bot.fetch_user(ctx.author.id)

        help_text = """
            📜 **MineFlat Bot Commands**

            `!ban [user]` — Ban Someone Perm.
            `!tempban [user] [duration]` — Temp ban someone (x t, t is the unit of measure for the time, d: day, h: hours, and m: minuites).
            `!kick [user]` — Just kicks someone.
            `!warn [user] [reason]` — Warn a user.

            More commands coming soon. The shrine expands with every update.
            """

        await mod.send(help_text)
    help_text = """
    📜 **MineFlat Bot Commands**
    
    `!help` — you just done it :wilted_rose:
    `!bugreport [description]` — Submit a bug and the developer will see it (in his dms, you can slide in lil bros dms).
    `!info` — Get info about the game.
    `!roast [user] [contex]` — Roast the user you mentioned in [user] and also base it off [contex] using google's AI gemini.
    `!roast_img [context]` — Roast the image you sent along with the msg and base it off [context] using google's AI gemini.
    `!compliment [user] [contex]` — compliment the user you mentioned in [user] and also base it off [contex] using google's AI gemini.
    `!compliment_img [context]` — compliment the image you sent along with the msg and base it off [context] using google's AI gemini.
    `!settings` — Change your settings
    `!promo [server name (when there are spaces do a _)] [invite link/code] [server description]` — Make a promotion for your discord server using google's AI gemini.
    `!shop [action] [action2]`  — Do anything related with shop, buying, viewing, etc
    `!guess [number]`  — Start the game with !guess then guess numbers with !guess [number]
    `!gamble [amount]`  — Gamble any amount of coins, you can either lose, double, or triple your money
    
    More commands coming soon. The bot expands with every update.
    """
    await ctx.send(help_text)

def add_punishment(user_id,punishment, start, end, reason):
    number = 0
    with open("punishment_logs.json",'r') as f:
        data = json.load(f)
    user = data[str(user_id)]
    for _ in user:
        number += 1
    target_str = {
        "start": start,
        "end": end,
        "reason": reason
    }
    user[number + 1] = {punishment: target_str}
    with open("punishment_logs.json", 'w') as f:
        json.dump(data, f, indent=2)

def log_punishment(user_id, guild_id, punishment_type, reason, expires=None, file_path="punishments.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    # Ensure user entry exists
    if str(user_id) not in data:
        data[str(user_id)] = []

    # Add new punishment
    data[str(user_id)].append({
        "guild_id": str(guild_id),
        "type": punishment_type,
        "reason": reason or "No reason provided",
        "timestamp": datetime.now().isoformat(),
        "expires": expires.isoformat() if expires else None
    })

    # Save back to file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await ctx.message.delete()
    user = await bot.fetch_user(member.id)
    await user.send(f'You have been kicked from `Mineflat Official Server` for reason `{reason}`')
    await member.kick(reason=reason)
    await ctx.send(f'{member} has been kicked')
    add_punishment(member.id,"kick",datetime.now().isoformat(timespec='seconds'),datetime.now().isoformat(timespec='seconds'),reason)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await ctx.message.delete()
    user = await bot.fetch_user(member.id)
    await user.send(f'You have been banned from `Mineflat Official Server` for reason `{reason}`')
    await member.ban(reason=reason)
    await ctx.send(f'{member} has been banned')
    log_punishment(member.id,ctx.guild,'Ban',reason)
    add_punishment(member.id,"ban",datetime.now().isoformat(timespec='seconds'),datetime.now().isoformat(timespec='seconds'),reason)



def remove_punishment(user_id, guild_id=None, punishment_type=None, file_path="punishments.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return False  # Nothing to remove

    user_key = str(user_id)
    if user_key not in data:
        return False  # No punishments for this user

    # Filter out matching punishments
    original_count = len(data[user_key])
    data[user_key] = [
        p for p in data[user_key]
        if not (
            (guild_id is None or p["guild_id"] == str(guild_id)) and
            (punishment_type is None or p["type"].lower() == punishment_type.lower())
        )
    ]

    # If all punishments removed, delete user entry
    if not data[user_key]:
        del data[user_key]

    # Save updated data
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

    return len(data.get(user_key, [])) < original_count

def parse_duration(input_str):
    # Example input: "5d 2h 30m"
    pattern = r'(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?'
    match = re.match(pattern, input_str.strip())

    if not match:
        return None  # Invalid format

    days = int(match.group(1)) if match.group(1) else 0
    hours = int(match.group(2)) if match.group(2) else 0
    minutes = int(match.group(3)) if match.group(3) else 0
    seconds = int(match.group(4)) if match.group(4) else 0

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

@bot.command()
@commands.has_permissions(ban_members=True)
async def tempban(ctx, member: discord.Member, duration: int, unit='h', *, reason=None):
    await ctx.message.delete()
    duration_seconds = duration
    unit = unit.lower()
    display_unit = 'Hours'

    # Convert duration to seconds
    if unit == 'd':
        display_unit = 'Days'
        duration *= 86400
    elif unit == 'h':
        display_unit = 'Hours'
        duration *= 3600
    elif unit == 'm':
        display_unit = 'Minutes'
        duration *= 60
    elif unit == 's':
        display_unit = 'Seconds'
        duration *= 1
    else:
        await ctx.send("Invalid time unit. Use `s`, `m`, `h`, or `d`.")
        return

    # DM before ban
    unban_time = datetime.now() + timedelta(seconds=duration)
    formatted_time = unban_time.strftime("%A, %B %d at %I:%M %p")

    try:
        await member.send(
            f"You will be unbanned on **{formatted_time}**.\n"
            f"Check back then to rejoin: https://discord.gg/qdG33SQWQv"
        )
    except discord.Forbidden:
        await ctx.send(f"Could not DM {member}. They may have DMs off or blocked the bot.")

    # Ban the user
    await member.ban(reason=reason)
    await ctx.send(f"{member.mention} has been tempbanned for {duration} seconds. Reason: `{reason or 'None'}`")

    log_punishment(member.id, ctx.guild, 'Ban', reason, unban_time)
    end = datetime.now() + parse_duration(f'{duration}{unit}')
    add_punishment(member.id,"tempban",datetime.now().isoformat(timespec='seconds'),end.isoformat(timespec='seconds'),reason)


    # Wait and unban

    await asyncio.sleep(duration)
    try:
        user = await bot.fetch_user(member.id)
        remove_punishment(member.id, ctx.guild, 'Ban')
        await ctx.guild.unban(user)
        try:
            await user.send(
                f"You are unbanned from \'Mineflat Official Server\'.\n"
                f"Check back then to rejoin: https://discord.gg/qdG33SQWQv"
            )

        except discord.Forbidden:
            await ctx.send(f"Could not DM {user} after unban.")
        await ctx.send(f"{member.mention} has been unbanned after {duration_seconds} {display_unit}.")
    except discord.NotFound:
        await ctx.send(f"Unban failed: {member} was not found in the ban list.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban_user(ctx, user_id: int, *, reason=None):
    await ctx.message.delete()
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f"{user} has been unbanned. Reason: `{reason or 'None'}`")
        remove_punishment(user.id, ctx.guild, 'Ban')

        try:
            await user.send(
                f"You have been unbanned from `{ctx.guild.name}`.\n"
                f"Rejoin here: https://discord.gg/qdG33SQWQv"
            )
        except discord.Forbidden as e:
            await ctx.send(f"Could not DM {user}. They may have DMs off or blocked the bot.")
    except discord.NotFound:
        await ctx.send("User not found in ban list. The shrine gate remains closed.")

@bot.command()
async def mute(ctx, user: discord.Member ,duration: int , unit='h', *, reason=None):
    await ctx.message.delete()
    if not ctx.author.guild_permissions.moderate_members:
        await ctx.send(f"{ctx.author.mention}, you lack authority to mute others.")
        return
    unit = unit.lower()
    save_duration = duration
    duration = int(duration)

    # Convert duration to seconds
    if unit == 'd':
        display_unit = 'Days'
        duration *= 86400
    elif unit == 'h':
        display_unit = 'Hours'
        duration *= 3600
    elif unit == 'm':
        display_unit = 'Minutes'
        duration *= 60
    elif unit == 's':
        display_unit = 'Seconds'
        duration *= 1
    else:
        await ctx.send("Invalid time unit. Use `s`, `m`, `h`, or `d`.")
        return
    try:
        duration = int(duration)
        duration = timedelta(seconds=duration)
        await user.timeout(duration,reason=reason)
        user = await bot.fetch_user(user.id)
        await user.send(f'You got muted for {save_duration} {display_unit} for {reason}')
    except Exception as e:
        print(e)
    end = datetime.now() + parse_duration(f'{save_duration}{unit}')
    add_punishment(user.id,"mute",datetime.now().isoformat(timespec='seconds'),end.isoformat(timespec='seconds'),reason)


@bot.command()
async def warn(ctx,member: discord.Member, * , reason):
    if not ctx.author.guild_permissions.moderate_members:
        await ctx.send(f"{ctx.author.mention}, you lack authority to warn others.")
        return
    await ctx.message.delete()
    await member.send(f'{ctx.author.display_name} has warned you for reason {reason}')
    add_punishment(member.id,"warn",datetime.now().isoformat(timespec='seconds'),datetime.now().isoformat(timespec='seconds'),reason)


@bot.command()
async def unmute(ctx,member: discord.Member,*,reason):
    if not ctx.author.guild_permissions.moderate_members:
        await ctx.send(f"{ctx.author.mention}, you lack authority to mute others.")
        return
    await ctx.message.delete()
    await member.edit(timed_out_until=None)
    user = await bot.fetch_user(member.id)
    await user.send(f'You got unmuted for {reason}')



@bot.command()
async def bugreport(ctx, *, description):
    print(f"[BUG REPORT] From {ctx.author}: {description}")
    user = await bot.fetch_user(1406075868786196591)
    await user.send(f'We got a bug report from {ctx.author}\n{description}')
    await ctx.send("📜 Bug report received. The shrine will investigate.")

def edit_line(filename, line_number, new_content):
    with open(filename, 'r') as f:
        lines = f.readlines()

    if line_number < 0 or line_number >= len(lines):
        raise IndexError("Line number out of range.")

    lines[line_number] = new_content + '\n'

    with open(filename, 'w') as f:
        f.writelines(lines)

def contains_short_fragment(text):
    words = str(text).lower().split()
    return any(fragment in words for fragment in short_fragments)

def contains_full_curse(text):
    return any(word in text.lower() for word in full_curse_words)

def detect_and_log_curses(user_id, content, full_curse_words, short_fragments):
    content = content.lower()
    curse_count = 0

    # Step 1: Detect short fragments as standalone words
    words = content.split()
    for word in words:
        if word in short_fragments:
            curse_count += 1

    # Step 2: Detect full curse words using substring match, avoiding reuse
    used = list(content)
    for curse in full_curse_words:
        idx = ''.join(used).find(curse)
        while idx != -1:
            curse_count += 1
            for i in range(idx, idx + len(curse)):
                used[i] = '*'  # Mark letters as used
            idx = ''.join(used).find(curse)

    return curse_count


def contains_muteable_word(message, muteable_words):
    # 1. Convert to lowercase
    message_lower = message.lower()

    # 2. Use a regular expression to find all words.
    # This splits the message by any non-alphanumeric character (including spaces and punctuation).
    # You might need to adjust this regex based on how you want to handle contractions/hyphens.
    words = re.findall(r'\b\w+\b', message_lower)

    # 3. Check for any match
    return any(word in muteable_words for word in words)

with open('XP/Storage/achivements.json') as f:
    achivements = json.load(f)['achivements']

def get_user_stats(user_id, type = 'all'):
    user_id = str(user_id)
    data_path = f'XP/Users/{user_id}'
    json_path = f'{data_path}/stats.json'
    if not os.path.exists(data_path):
        os.mkdir(data_path)

        default = {
            "Messages": 0,
            "Commands": 0,
            "Curses": 0,
            "XP": 0,
            "Level": 0,
            "Achivements": []
        }

        with open(json_path,'w') as f:
            json.dump(default,f,indent = 4)
    with open(json_path) as f:
        stats = json.load(f)
        return stats if type == 'all' else stats[type]

def save_user_stats(user_id, stats):
    json_path = f'XP/Users/{str(user_id)}/stats.json'
    with open(json_path, 'w') as f:
        json.dump(stats, f, indent=4)

def levelup_check(level):
    return int(((level + 1) ** 2) * 50)

def xp_for_next_level(user_id):
    stats = get_user_stats(user_id)
    current_level = stats["Level"]
    next_level = current_level + 1
    required_xp = int((next_level ** 2) * 50)
    return required_xp

def add_xp(user_id, earned_xp, stats):
    stats = stats
    stats["XP"] += earned_xp
    lvl = stats["Level"]

    while stats["XP"] >= levelup_check(stats["Level"]):
        stats["XP"] -= levelup_check(stats["Level"])
        stats["Level"] += 1
        print(f"{user_id} leveled up to {stats['Level']}!")

    return stats


async def check_achivement(user_id, stats):
    stats = stats
    guild = bot.get_guild(1411439308778246297)
    gotten_achivements = stats['Achivements']
    for achivement in achivements:
        achivement = achivements[achivement]
        requirement = achivement['Requirement']
        rewards = achivement['Reward']
        if requirement['Type'] == 'message':
            if int(stats['Messages']) >= int(requirement['Amount']) and not achivement['Name'] in gotten_achivements:
                gotten_achivements.append(achivement['Name'])
                for reward in rewards["Types"]:
                    if reward == 'XP':
                        lvl = stats["Level"]
                        stats = add_xp(user_id, int(rewards["Types"][reward]), stats)
                        nlvl = stats['Level']

                        if nlvl > lvl:
                            author = bot.get_user(user_id)
                            avatar = author.avatar.url if author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

                            LVL_CHANNEL = bot.get_channel(1423054390880764135)

                            embed = discord.Embed(
                                title=f"{author.display_name} Leveled up",
                                description=f'🔼 {author.mention} Leveled up from **{lvl}** to **{nlvl}** 🔼',
                                color=discord.Color.red()
                            )
                            embed.set_thumbnail(url=avatar)  # Shows profile picture
                            embed.set_footer(text=f"You need {xp_for_next_level(author.id)} XP to level up again!")
                            await LVL_CHANNEL.send(f'{author.mention}', embed=embed)
                    elif reward == 'Role':
                        member = guild.get_member(user_id)
                        if member:
                            role = guild.get_role(rewards["Types"][reward])
                            await member.add_roles(role)

    stats['Achivements'] = gotten_achivements
    return stats

@bot.command()
async def achievement(ctx,*, type: str = 'None'):
    user = ctx.author
    stats = get_user_stats(user.id)
    avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

    lower = []
    for _ in achivements:
        lower.append(str(_).lower())

    if not type.lower() in ('all', 'none') + tuple(lower):
        await ctx.reply(f'`{type}` is\'t a valid command, choose a achievement name to view a certain achievement, or all or nothing to see a list of them')
        return
    if type in ('None', 'all'):
        embed = discord.Embed(
            title=f"{user.display_name} Achievements",
            description=f'{user.mention} Achievements',
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=avatar)  # Shows profile picture
        for achievement in achivements:
            achievement = achivements[achievement]
            name = achievement['Name']
            requirement = achievement['Requirement']
            rewards = achievement['Reward']['Types']

            visual_rewards = ''

            for reward in rewards:
                if reward == 'XP':
                    visual_rewards += f'\n{rewards[reward]} XP'
                elif reward == 'Role':
                    guild = bot.get_guild(1411439308778246297)
                    visual_rewards += f'\nRole:{guild.get_role(rewards[reward]).mention}'

            progress = int(stats['Messages']) / int(requirement['Amount'])
            bar = '█' * int(progress * 10) + '░' * (10 - int(progress * 10))

            embed.add_field(name=f'{"✅" if achievement["Name"] in stats["Achivements"] else "❌"} {name}\n' + f"{bar} ({stats['Messages']}/{requirement['Amount']})",value=f'{requirement["Visual"]}\n\nRewards{visual_rewards}')

        await ctx.reply(embed=embed)

    if type in achivements:
        embed = discord.Embed(
            title=type,
            description=f'{type} Achievements',
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=avatar)  # Shows profile picture
        achievement = achivements[type]
        name = achievement['Name']
        requirement = achievement['Requirement']
        rewards = achievement['Reward']['Types']

        visual_rewards = ''

        for reward in rewards:
            if reward == 'XP':
                visual_rewards += f'\n{rewards[reward]} XP'
            elif reward == 'Role':
                guild = bot.get_guild(1411439308778246297)
                visual_rewards += f'\nRole:{guild.get_role(rewards[reward]).mention}'

        progress = int(stats['Messages']) / int(requirement['Amount'])
        bar = '█' * int(progress * 10) + '░' * (10 - int(progress * 10))

        embed.add_field(
            name=f'{"✅" if achievement["Name"] in stats["Achivements"] else "❌"} {name}\n' + f"{bar} ({stats['Messages']}/{requirement['Amount']})",
            value=f'{requirement["Visual"]}\n\nRewards{visual_rewards}')
        await ctx.reply(embed=embed)


@bot.event
async def on_message(message):
    global number, countedlast

    # Access message content and sender
    author = message.author
    content = message.content
    message_id = message.id
    guild = message.guild
    guild_id = guild.id
    channel = message.channel
    user_id = message.author.id
    avatar = author.avatar.url if author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

    # Ignore messages sent by bots (including itself)
    if message.author.bot:
        try:
            curse = pplcurseamt[str(user_id)]
        except KeyError:
            pplcurseamt[str(user_id)] = 0
            curse = 0
            with open("pplcurse.json", 'w') as f:
                json.dump(pplcurseamt, f, indent=4)

        curse += detect_and_log_curses(user_id, content, full_curse_words, short_fragments)
        new_curse = detect_and_log_curses(user_id, content, full_curse_words, short_fragments)

        if new_curse > 0:
            text = f"{author.mention} said {curse} curse word{'s' if curse > 1 else ''}"
            pplcurseamt[str(user_id)] = curse
            with open("pplcurse.json", 'w') as f:
                json.dump(pplcurseamt, f, indent=4)
            await channel.send(text)
        return

    if contains_muteable_word(content,muteable_words):
        r9 = {}
        with open("hate_speech.json") as f:
            r9 = json.load(f)

        if not str(user_id) in r9:
            r9[str(user_id)] = 0
        r9[str(user_id)] = int(r9[str(user_id)]) + 1

        duration = timedelta(minutes=(15 * int(r9[str(user_id)])) * 2)
        end = datetime.now() + duration
        add_punishment(user_id, "mute", datetime.now().isoformat(timespec='seconds'),end.isoformat(timespec='seconds'), "Inappropriate Language")

        with open("hate_speech.json", 'w') as f:
            json.dump(r9, f, indent=4)

        await channel.send(f"{author.mention}, sorry but your message breaks the rules")
        await author.timeout(duration, reason="Inappropriate language")
        return

    if len(content) > 1900:
        await message.reply(f'That message contains {len(content)} characters, wtf is that yap')

    if channel.id == 1413971808411193455:
        if safe_int(content[0]) is not None:
            if not countedlast == user_id:
                if content == str(number + 1):
                    await message.add_reaction("✅")
                    number += 1
                    with open('lastcounter','w') as f:
                        f.write(str(user_id))
                    with open('Number','w') as f:
                        f.write(str(number))
                    countedlast = user_id
                else:
                    number = 0
                    embed = discord.Embed(
                        title=f"Fucking Idiot here: {author.display_name}",
                        description=f"{author.mention} This loser dont know how to count\n",
                        color=discord.Color.red()
                    )
                    embed.set_thumbnail(url=avatar)  # Shows profile picture
                    embed.set_footer(text=f"This fucking idiot {author.display_name} prob still in elementary school")
                    await message.add_reaction("❌")
                    await message.reply(embed=embed)
                    await channel.send('Number is back to 0')
                    with open('Number','w') as f:
                        f.write(str(number))
            else:
                await message.reply('can\'t count 2 times in a row :wilted_rose:')


    try:
        curse = pplcurseamt[str(user_id)]
    except KeyError:
        pplcurseamt[str(user_id)] = 0
        curse = 0
        with open("pplcurse.json",'w') as f:
            json.dump(pplcurseamt,f,indent=4)

    curse += detect_and_log_curses(user_id, content, full_curse_words, short_fragments)
    new_curse = detect_and_log_curses(user_id, content, full_curse_words, short_fragments)

    if new_curse > 0:
        text = f"{author.mention} said {curse} curse word{'s' if curse > 1 else ''}"
        pplcurseamt[str(user_id)] = curse
        with open("pplcurse.json",'w') as f:
            json.dump(pplcurseamt,f,indent=4)
        await channel.send(text)

    stats = get_user_stats(user_id)
    lvl = stats["Level"]
    base_xp = 5
    bonus_xp = 0.05 * len(content) + new_curse * 0.5
    stats = add_xp(user_id, base_xp + bonus_xp, stats)
    nlvl = get_user_stats(user_id, 'Level')

    if nlvl > lvl:
        LVL_CHANNEL = bot.get_channel(1423054390880764135)

        embed = discord.Embed(
            title=f"{author.display_name} Leveled up",
            description=f'🔼 {author.mention} Leveled up from **{lvl}** to **{nlvl}** 🔼',
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=avatar)  # Shows profile picture
        embed.set_footer(text=f"You need {xp_for_next_level(author.id)} XP to level up again!")
        # await LVL_CHANNEL.send(f'{author.mention}', embed=embed)

    stats['Messages'] += 1
    if content[0] == '!':
        stats['Commands'] += 1
    stats['Curses'] += new_curse

    old_achivements = stats['Achivements']
    stats = await check_achivement(user_id, stats)
    new_achivements = stats['Achivements']
    achivement_CHANNEL = bot.get_channel(1423104226959032361)

    for achivement in new_achivements:
        if not achivement in old_achivements:
            a_stats = achivements[achivement]
            embed = discord.Embed(
            title=f"{author.display_name} Got an achievement",
            description=f'{author.mention} Got the achievement \"{achivement}\"',
            color=discord.Color.red()
            )
            embed.set_thumbnail(url=avatar)  # Shows profile picture
            embed.set_footer(text=f"Great Job")
            await achivement_CHANNEL.send(f'{author.mention}', embed=embed)

    save_user_stats(user_id, stats)

    # VERY IMPORTANT: if you override on_message, you must manually process commands
    if not locked:
        await bot.process_commands(message)
    elif user_id == 1406075868786196591:
        await bot.process_commands(message)

with open('Storage/Suffixes') as f:
    suffixes = [''] + [line.strip() for line in f if line.strip()]

def format_count(n):
    """
    Formats large numbers with K, M, B suffixes.
    This is a robust fallback for suffix_number if it's not defined.
    """
    if n is None:
        return '0'
    n = math.floor(n)
    if abs(n) < 1000:
        return f"{n:,}"

    # Use standard list of suffixes (can be expanded if neededd

    # Handle negative numbers by processing absolute value and adding sign back later
    sign = '-' if n < 0 else ''
    n = abs(n)

    if n == 0:
        return '0'

    i = 0
    while n >= 1000 and i < len(suffixes) - 1:
        n /= 1000.0
        i += 1

    # Format to one decimal place, unless it's a small integer
    if i > 0:
        return f"{sign}{n:,.1f}{suffixes[i]}"
    else:
        return f"{sign}{n:,}"


def load_all_stats():
    """
    Loads and merges stats from multiple specified directories
    (e.g., XP and Block Tycoon data).
    """
    # List of directories to search for user folders (from your final version)
    directarys = ["XP/Users/", "Block Tycoon/players/"]
    users = {}

    for directary in directarys:
        # Check if the directory exists before listing files for robustness
        if not os.path.exists(directary):
            print(f"Warning: Stat directory not found at {directary}")
            continue

        for user_folder in os.listdir(directary):
            user_id = user_folder  # The user ID is the folder name
            stats_filepath = f'{directary}{user_id}/stats.json'

            if os.path.exists(stats_filepath):
                try:
                    # Initialize user entry if not present
                    if user_id not in users:
                        users[user_id] = {}

                    with open(stats_filepath, 'r') as f:
                        items = json.load(f)

                        # Merge new items into the existing user stats
                        for item, value in items.items():
                            # Overwrite is fine if stats have the same name, or merge unique ones
                            users[user_id][item] = value
                except Exception as e:
                    print(f"Error loading stats for user {user_id} from {directary}: {e}")
                    continue

    return users


def split_dict(data):
    """
    Transposes the user-keyed dictionary into a stat-keyed dictionary.
    Output: { 'StatName': {'id_A': 300, 'id_B': 50}, ... }
    """
    dicts = {}

    for user_id, stats in data.items():
        for stat_name, value in stats.items():
            if stat_name not in dicts:
                dicts[stat_name] = {}

            # Map stat name to a dictionary of {user_id: value}
            dicts[stat_name][user_id] = value

    return dicts


def ordinal(n):
    """Returns the ordinal string for a number (1st, 2nd, 3rd, 4th, etc.)."""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


# --- Leaderboard Command ---

@bot.command(aliases=['lb', 'top'])
async def leaderboard(ctx, stat_type: str = "Messages"):
    """
    Shows the top users for a specified statistic, gathering data
    from all available sources.
    """
    author = ctx.author

    # Send initial message to indicate processing is starting
    message = await ctx.send("⌛ Loading user data and preparing the scoreboard...")

    # Determine author avatar URL
    avatar = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url

    # Use asyncio and bot.loop.run_in_executor for I/O-heavy loading
    user_stats_dict = await asyncio.to_thread(load_all_stats)  # Using asyncio.to_thread for Python 3.9+

    if not user_stats_dict:
        await message.edit(content="No user statistics found from any data source.")
        return

    stats = split_dict(user_stats_dict)

    # 1. Identify, Filter, and Sort Numeric Stats
    numeric_stats = {}
    all_stats = []

    for name, user_data in stats.items():
        try:
            # Check if the data type is numeric by checking the first value
            first_key, first_value = next(iter(user_data.items()))

            if isinstance(first_value, (int, float)):
                all_stats.append(name)

                # Create a list of (user_id_int, value) tuples for sorting
                sortable_list = []
                for uid_str, val in user_data.items():
                    if isinstance(val, (int, float)):
                        sortable_list.append((int(uid_str), val))

                # Sort the list (Highest value first)
                sorted_list = sorted(sortable_list, key=lambda item: item[1], reverse=True)
                numeric_stats[name] = sorted_list
        except StopIteration:
            continue
        except ValueError:
            continue

    # 2. Validation Check
    if stat_type not in numeric_stats:
        send = f'`{stat_type}` is not a valid stat. Valid numeric stats are:\n'
        for name in sorted(all_stats):
            send += f'`{name}`\n'
        await message.edit(content=send)
        return

    sorted_data = numeric_stats[stat_type]

    # 3. Create and Populate the Embed
    embed = discord.Embed(
        title=f"🏆 Server Leaderboard: {stat_type}",
        description=f'The top 10 people with the most **{stat_type}**!',
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=avatar)

    ranks_users = []
    counts = []
    author_rank = None

    # Iterate over all sorted data to find ranks, but only display the top 10
    for i, (user_id, raw_count) in enumerate(sorted_data):
        rank = i + 1

        # --- Display Logic (Top 10) ---
        if rank <= 10:
            user = ctx.bot.get_user(user_id)
            # Use mention if user object is found, otherwise fallback to ID
            username_display = user.mention if user else f"<@{user_id}>"

            # Format the count using the helper function
            count_display = format_count(raw_count)

            ranks_users.append(f"**{ordinal(rank)}** {username_display}")
            counts.append(count_display)

        # --- Author Rank Check ---
        if user_id == ctx.author.id:
            author_rank = rank
            # Stop if the author is in the top 10, otherwise keep checking
            if author_rank <= 10:
                pass  # Continue to make sure all top 10 fields are added

    if ranks_users:
        embed.add_field(name="Rank & User", value='\n'.join(ranks_users), inline=True)
        embed.add_field(name=stat_type, value='\n'.join(counts), inline=True)
    else:
        embed.description = f"No users found with a recorded value for **{stat_type}**."

    # 4. Set Footer
    if author_rank is not None:
        # The author is in the leaderboard
        author_value = sorted_data[author_rank - 1][1]  # -1 because list is 0-indexed
        author_count_display = format_count(author_value)

        embed.set_footer(
            text=f"{author.display_name}'s Rank: {ordinal(author_rank)} | {stat_type}: {author_count_display}")
    else:
        # The author is not in the data set (or value is 0/default)
        embed.set_footer(text=f"You are not currently ranked for {stat_type}.")

    await message.edit(content=None, embed=embed)

def get_mime_type_from_url(url):
    try:
        mime_type, _ = mimetypes.guess_type(url)
        return mime_type if mime_type else "image/jpeg"
    except Exception:
        return "image/jpeg"



def load_punishments(file_path="punishments.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        return {}  # No punishments yet

def get_user_punishments(user_id, file_path="punishments.json"):
    data = load_punishments(file_path)
    return data.get(str(user_id), [])

def get_user_punishment_types(user_id, file_path="punishments.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []

    punishments = data.get(str(user_id), [])
    return [p['type'] for p in punishments if 'type' in p]

class AppealDecisionView(View):
    def __init__(self, user: discord.User, server = 1411439308778246297):
        super().__init__(timeout=300)  # Optional timeout
        self.user = user
        self.guild = server

    @discord.ui.button(label="Accept Appeal", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("✅ Appeal accepted.", ephemeral=True)
        try:
            await self.user.send("Your punishment appeal has been **accepted**. You may rejoin or resume activity.")
            guild = bot.get_guild(self.guild)
            if 'Ban' in get_user_punishment_types(self.user.id):
                await guild.unban(discord.Object(id=self.user.id), reason="Your appeal got accepted")
                remove_punishment(self.user.id,bot.get_guild(self.guild),"Ban")
        except discord.Forbidden:
            await interaction.followup.send("Could not DM the user. They may have DMs off.", ephemeral=True)

    @discord.ui.button(label="Deny Appeal", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ Appeal denied.", ephemeral=True)
        try:
            await self.user.send("Your punishment appeal has been **denied**. Please wait until your punishment expires.")
        except discord.Forbidden:
            await interaction.followup.send("Could not DM the user. They may have DMs off.", ephemeral=True)

@bot.command()
async def appeal(ctx, *, reason):
    channel = ctx.channel
    guild = ctx.guild
    punishment = get_user_punishments(ctx.author.id)

    if guild.id == 1413009300321996832:
        if channel.id == 1413889547833577512:
            if not punishment:
                await ctx.send("You dont have any ongoing punishments")
                return
            user = await bot.fetch_user(1406075868786196591)
            view = AppealDecisionView(ctx.author,1411439308778246297)
            await user.send(f'{ctx.author.display_name} appealed to punishment {get_user_punishment_types(ctx.author.id)}\n\n{reason}',view=view)
            await ctx.send("The founder got dmed you appeal, meanwhile have fun in the general")

async def fetch_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.read()

def chunkify_text(text, max_length=1900):
    lines = text.split('\n')
    chunks = []
    current_chunk = ""

    for line in lines:
        # Add newline back when joining
        if len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += ("\n" if current_chunk else "") + line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

active_guess_games = {}

def get_coins(user_id):
    data = {}
    user_id = str(user_id)
    with open("Coins.json") as f:
        data = json.load(f)
    try:
        user_coins = data[user_id]
        return user_coins
    except:
        user_coins = 0
        user = bot.get_user(int(user_id))
        data[user_id] = 0
        with open("Coins.json", 'w') as f:
            json.dump(data, f, indent=4)
        return user_coins

def update_coins(user_id, type, amount = 0):
    user_id = str(user_id)

    if type not in ('a', 'w', 'r', '0'):
        return

    user_coins = get_coins(user_id)

    with open("Coins.json") as f:
        data = json.load(f)

    if type == 'a':
        data[user_id] = user_coins + amount
    elif type == 'w':
        data[user_id] = amount
    elif type == 'r':
        data[user_id] = user_coins - amount
    elif type == '0':
        data[user_id] = 0

    with open("Coins.json", 'w') as f:
        json.dump(data, f, indent=4)


@bot.command()
@commands.has_role("Economy Mod")
async def update_user_coins(ctx, user: discord.Member, type: str, amount: int = 0):
    if type not in ('a', 'w', 'r', '0'):
        await ctx.send(f'Type `{type}` Is not valid, valid types are \n---- a: add\n---- r: remove\n---- w: write\n---- 0: reset')
        return

    user_id = user.id
    await ctx.send(f'Updating {bot.get_user(user_id).display_name} Coins')
    update_coins(user_id, type, amount)
    await ctx.send(f'Updated {bot.get_user(user_id).display_name} Coins to {get_coins(user_id)}')

@bot.command()
async def pay(ctx, user: discord.Member, amount: int):
    cash = get_coins(ctx.author.id)
    if int(cash) < amount:
        await ctx.reply('Bro you dont have that much')
        return
    if int(amount) < 0:
        await ctx.reply('Im not letting that glitch happen again')
        return
    update_coins(ctx.author.id, 'r', amount)
    update_coins(user.id, 'a', amount)
    await ctx.reply(f'Successfully payed {user.mention} {amount} coins')

@bot.command()
@commands.has_role("Economy Mod")
async def job_assign(ctx, member: discord.Member, *, job: str):
    with open("Jobs.json") as f:
        alljobs = json.load(f)
    users = alljobs['Users']
    jobs = alljobs['Jobs']

    if job not in jobs:
        await ctx.reply("That job doesn't exist.")
        return

    users[str(member.id)] = job
    alljobs['Users'] = users
    with open("Jobs.json", "w") as f:
        json.dump(alljobs, f, indent=4)

    await ctx.reply(f"{member.mention} has been forcibly assigned the job **{job}**.")

def calculate_owed(original_amount, start_time, additional_amount=0):
    start_rate = 1.05       # Initial debt: 105%
    hourly_growth = 1.01    # 1% interest per hour

    total_principal = original_amount + additional_amount
    elapsed_hours = (time.time() - start_time) / 3600

    owed = total_principal * start_rate * (hourly_growth ** elapsed_hours)
    return math.floor(owed)



@bot.command()
async def loan(ctx, type = 'apple', amount: int = 0):
    user_id = str(ctx.author.id)
    type = type.lower()
    if not type in ('take','pay','view'):
        await ctx.reply("Invalid command, Valid commands are\n`!loan take [amount]` Take a loan\n`!loan pay [amount]` Pay a amount of your loan\n`!loan view` see your current loan")
    with open("Loans.json") as f:
        loans = json.load(f)
    if type == 'take':
        if not user_id in loans:
            loans[user_id] = {
                "Owe": 0,
                "time": time.time(),
                "original": amount,
                'add': -amount
                              }
        loans[user_id] = {
            "Owe": calculate_owed(loans[user_id]['original'],loans[user_id]["time"], loans[user_id]['add'] + amount),
            "time": loans[user_id]['time'],
            "original": loans[user_id]['original'],
            "add": loans[user_id]['add'] + amount
        }

        with open("Loans.json", "w") as f:
            json.dump(loans, f, indent=4)
        update_coins(user_id,'a',amount)
        await ctx.reply(f'Successfully loaned {amount} coins\nYou now owe {loans[user_id]["Owe"]}')
    if type == 'pay':
        if not user_id in loans:
            await ctx.reply('You dont have any ongoing loans')
            return
        loans[user_id] = {
            "Owe": calculate_owed(loans[user_id]['original'] - amount,loans[user_id]["time"], loans[user_id]['add']),
            "time": loans[user_id]['time'],
            "original": loans[user_id]['original'] - amount,
            "add": loans[user_id]['add']
        }
        start_time = loans[user_id]['time']
        elapsed_hours = round((time.time() - start_time) / 3600)
        update_coins(user_id,'r',amount)
        if loans[user_id]['Owe'] == 0:
            await ctx.reply(f'You payed off you loan\nafter {elapsed_hours} hours')
            del loans[user_id]
        else:
            await ctx.reply(f'You payed off {amount} of you loan\nYou now owe {loans[user_id]["Owe"]}')
        with open("Loans.json", "w") as f:
            json.dump(loans, f, indent=4)
    if type == 'view':
        if user_id not in loans:
            await ctx.reply("You have no ongoing loans.")
            return
        loans[user_id] = {
            "Owe": calculate_owed(loans[user_id]['original'],loans[user_id]["time"], loans[user_id]['add']),
            "time": loans[user_id]['time'],
            "original": loans[user_id]['original'],
            "add": loans[user_id]['add']
        }
        loan = loans[user_id]
        await ctx.reply(
            f'## {ctx.author.display_name}\'s Current Loan\n'
            f'### • **Owes:** {loan["Owe"]}\n'
            f'### • **Loan Hours:** {round((time.time() - loan["time"]) / 3600)}\n'
            f'### • **Remaining Money:** {loan["original"] + loan["add"]}'
                        )

toofastphrases = ['Take a chill pill, no need to be that eager to work.', 'Little bro have a job in 2025.', 'Rest, just rest.', 'You cant just work over and over again IRL to stack money.', 'This time dont loot the boss.']

@bot.command()
async def job(ctx, action: str, *, job: str = 'None'):
    avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    if not action.lower() in ('apply', 'leave','view', 'work', 'stats'):
        await ctx.send('Invalid option, valid options are\n`!job apply [job]` — Apply for a job\n`!job leave` — Leave your current job\n`!job view` — See all jobs\n`!job work` — Work a shift of your job')
    with open("Jobs.json") as f:
        alljobs = json.load(f)
    with open("JobWork.json") as f:
        work_times = json.load(f)
    users = alljobs['Users']
    jobs = alljobs['Jobs']

    if not str(ctx.author.id) in users:
        users[ctx.author.id] = None
        alljobs["Users"] = users
        with open('Jobs.json','w') as f:
            json.dump(alljobs, f, indent=4)
    if not str(ctx.author.id) in work_times['time']:
        work_times['time'][ctx.author.id] = 0
        with open('JobWork.json','w') as f:
            json.dump(work_times, f, indent=4)
    if not str(ctx.author.id) in work_times['amount']:
        work_times['amount'][ctx.author.id] = 0
        with open('Jobs.json','w') as f:
            json.dump(work_times, f, indent=4)

    if action.lower() == 'view':
        embed = discord.Embed(title="📜 Available Jobs", color=discord.Color.gold())
        for name, data in jobs.items():
            embed.add_field(
                name=f"🧰 {name}",
                value=f"**Description:** {data['description']}\n**Salary:** {data['mincoins']}–{data['maxcoins']} coins\n**Cooldown:** {data['cooldown']} minutes\n**Require:** {data['require']} Shifts\n\ndo `!job apply {name}` to apply",
                inline=False
            )
        await ctx.send(embed=embed)
    if action.lower() == 'apply':
        if not job in jobs:
            await ctx.reply('Please send a valid job')
            return
        if not users[str(ctx.author.id)] is None:
            await ctx.reply(f'You have a job, Leave it with `!job leave`')
            return
        if work_times['amount'][str(ctx.author.id)] < jobs[job]["require"]:
            await ctx.reply(f'You dont have enough Shifts\nYou need {jobs[job]["require"]} Shifts but you only have {work_times["amount"][str(ctx.author.id)]} Shifts')
            return
        job_get_chance = jobs[job]["chance"]
        job_deny_chance = 100 - int(jobs[job]["chance"])
        outcome = random.choices(
            ["Hire","Deny"],
            weights=[job_get_chance, job_deny_chance],
            k=1
        )[0]
        if outcome == 'Hire':
            await ctx.reply('You Got Hired!\nDo your job with !job work')
            users[str(ctx.author.id)] = job
            alljobs['Users'] = users
            alljobs['Jobs'] = jobs
            with open('Jobs.json', 'w') as f:
                json.dump(alljobs, f, indent=4)
        if outcome == 'Deny':
            await ctx.reply('You Got Denied')
    if action.lower() == 'work':
        if users[str(ctx.author.id)] is None:
            await ctx.reply('You dont have a job, Apply for one with `!job apply [job]`')
            return
        last_work_time = work_times["time"][str(ctx.author.id)]
        now = time.time()
        cooldown_seconds = int(jobs[users[str(ctx.author.id)]]["cooldown"]) * 60
        elapsed = now - last_work_time
        remaining = cooldown_seconds - elapsed

        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            await ctx.reply(
                f"{random.choice(toofastphrases)}\nYou can work again in {minutes}m {seconds}s.")
            return

        work_times['time'][str(ctx.author.id)] = time.time()
        work_times['amount'][str(ctx.author.id)] = int(work_times['amount'][str(ctx.author.id)]) + 1
        with open('JobWork.json', 'w') as f:
            json.dump(work_times, f, indent=4)
        cash = random.randint(jobs[users[str(ctx.author.id)]]['mincoins'], jobs[users[str(ctx.author.id)]]['maxcoins'])
        update_coins(ctx.author.id, 'a', cash)
        await ctx.reply(f'You got {cash} coins this shift\nYou now have {get_coins(ctx.author.id)}')
    if action.lower() == 'leave':
        if users[str(ctx.author.id)] is None:
            await ctx.reply('You dont have a job, Apply for one with `!job apply [job]`')
            return
        await ctx.reply(f'You left your job as a {users[str(ctx.author.id)]}')
        users[ctx.author.id] = None
        alljobs['Users'] = users
        alljobs['Jobs'] = jobs
        with open('Jobs.json', 'w') as f:
            json.dump(alljobs, f, indent=4)
    if action.lower() == 'stats':
        embed = discord.Embed(title=f"{ctx.author.display_name} Job Status", color=discord.Color.gold())
        embed.add_field(
            name=f"**Job:** {users[str(ctx.author.id)]}",
            value=f"",
            inline=False
        )
        embed.add_field(
            name=f"**Worked Shifts:** {work_times['amount'][str(ctx.author.id)]}",
            value=f"",
            inline=False
        )
        embed.set_thumbnail(url=avatar)
        await ctx.send(embed=embed)

@bot.command()
async def guess(ctx, number = None):
    if not ctx.author.id in active_guess_games:
        avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        embed = discord.Embed(
            title=f"{ctx.author.display_name} Number Guessing Game",
            description=f"Im thinking of a number from 1-100 try guessing it. Use !guess Number to guess",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=avatar)  # Shows profile picture
        msg = await ctx.send(embed=embed)

        active_guess_games[ctx.author.id] = {
            "message": msg,
            "attempts": 0,
            "number": random.randint(1,100)
        }
    else:
        if safe_int(number) is None:
            await ctx.message.delete()
            avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
            embed = discord.Embed(
                title=f"{ctx.author.display_name} Number Guessing Game",
                description=f"Please Send A Valid Number\nIm thinking of a number from 1-100 try guessing it. Use !guess Number to guess",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=avatar)  # Shows profile picture
            msg = await ctx.fetch_message(active_guess_games[ctx.author.id]["message"].id)
            await msg.edit(embed=embed)
        else:
            await ctx.message.delete()
            number = int(number)
            target = int(active_guess_games[ctx.author.id]["number"])
            attempts = active_guess_games[ctx.author.id]["attempts"]
            if number > target:
                avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
                embed = discord.Embed(
                    title=f"{ctx.author.display_name} Number Guessing Game",
                    description=f"# Too Big Try Again\nIm thinking of a number from 1-100 try guessing it. Use !guess Number to guess",
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=avatar)  # Shows profile picture
                msg = await ctx.fetch_message(active_guess_games[ctx.author.id]["message"].id)
                await msg.edit(embed=embed)
                active_guess_games[ctx.author.id]["attempts"] = int(active_guess_games[ctx.author.id]["attempts"]) + 1
            if number < target:
                avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
                embed = discord.Embed(
                    title=f"{ctx.author.display_name} Number Guessing Game",
                    description=f"# Too Small Try Again\nIm thinking of a number from 1-100 try guessing it. Use !guess Number to guess",
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=avatar)  # Shows profile picture
                msg = await ctx.fetch_message(active_guess_games[ctx.author.id]["message"].id)
                await msg.edit(embed=embed)
                active_guess_games[ctx.author.id]["attempts"] = int(active_guess_games[ctx.author.id]["attempts"]) + 1
            if number == target:
                active_guess_games[ctx.author.id]["attempts"] = int(active_guess_games[ctx.author.id]["attempts"]) + 1
                attempts += 1
                avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
                amount = 25 - attempts
                if amount < 5:
                    amount = 5
                embed = discord.Embed(
                    title=f"{ctx.author.display_name} Number Guessing Game",
                    description=f"# You Got It\nYou Got {amount} Coins\nTook you {attempts} tries",
                    color=discord.Color.red()
                )
                update_coins(ctx.author.id,'a',amount)
                embed.set_thumbnail(url=avatar)  # Shows profile picture
                msg = await ctx.fetch_message(active_guess_games[ctx.author.id]["message"].id)
                await msg.edit(embed=embed)
                del active_guess_games[ctx.author.id]

# class Emoji(View):
#     def __init__(self, user_id):
#         super().__init__(timeout=60)
#
#
# @bot.command()
# async def diff_emoji(ctx, number = None):

@bot.command()
async def gamble(ctx,amount = None):
    if safe_int(amount) is None:
        await ctx.reply('Please enter a valid number')
        return

    amount = int(amount)

    if get_coins(ctx.author.id) < amount:
        await ctx.reply("You don't have enough coins for that.")
        return
    if amount < 0:
        await ctx.reply("Send a number higher than 0")
        return


    outcome = random.choices(
        ["triplewin", "win", "lose"],
        weights=[5, 45, 50],  # 5% triplewin, 45% win, 50% lose
        k=1
    )[0]
    avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

    embed = discord.Embed(
        title=f"{ctx.author.display_name} Gamble",
        description=f"You are gambling {amount} coins",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=avatar)
    msg = await ctx.send(embed=embed)
    update_coins(ctx.author.id,'r',amount)
    await asyncio.sleep(2)

    if outcome == "triplewin":
        await msg.add_reaction("💰")
        update_coins(ctx.author.id,'a',amount * 3)
        outcome = "**TRIPLE WIN**"
    elif outcome == "win":
        await msg.add_reaction("🪙")
        update_coins(ctx.author.id, 'a', amount * 2)
        outcome = "**WIN**"
    else:
        await msg.add_reaction("💀")
        update_coins(founder_id, 'a', amount)
        outcome = "**LOSE**"


    embed = discord.Embed(
        title=f"{ctx.author.display_name} Gamble",
        description=f"You got a {outcome}!\nYou now have {get_coins(ctx.author.id)}",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=avatar)
    await msg.edit(embed=embed)

    if amount == 0:
        await ctx.reply("Why did you gamble 0 coins XD")


async def grant_channel_access(ctx, user: discord.Member, channel_id: int):
    channel = bot.get_channel(channel_id)
    if not channel:
        print("❌ Channel not found.")
        return

    overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    try:
        await channel.set_permissions(user, overwrite=overwrite)
        await asyncio.sleep(1)  # Let Discord propagate
    except Exception as e:
        print(f"❌ Failed to set permissions: {e}")



@bot.command()
async def shop(ctx, type = 'page',*, thing = 1):
    with open("Shop.json") as f:
        shop = json.load(f)
    page_items = shop
    if type == 'page':
        thing = int(thing) - 1

        if thing * 2 > len(shop):
            thing = len(shop) - 4
        if thing <= 0:
            thing = 0

        shop_items = list(shop.items())
        page_items = shop_items[thing * 2: thing * 2 + 2]
    if type == 'buy':
        cost = shop[thing]["Cost"]
        if shop[thing]["Type"] == 'Role':
            if not int(get_coins(ctx.author.id)) > int(cost):
                await ctx.reply("Not enough money :wilted_rose:")
                return
            update_coins(ctx.author.id,'r',int(cost))
            role = ctx.guild.get_role(int(shop[thing]["ID"]))
            await ctx.author.add_roles(role)
            await ctx.reply(f"Successfully Bought {thing}")
        if shop[thing]["Type"] == 'Channel':
            if not int(get_coins(ctx.author.id)) > int(cost):
                await ctx.reply("Not enough money :wilted_rose:")
                return
            update_coins(ctx.author.id,'r',int(cost))
            channel = ctx.guild.get_channel(int(shop[thing]["ID"]))
            await ctx.reply(f"Successfully Bought {thing}")
            await grant_channel_access(ctx,ctx.guild.get_member(ctx.author.id),channel.id)

        return

    text = f'Current Balance:{get_coins(ctx.author.id)}\n'
    for _ in page_items:
        _ = _[0]
        text += f'## {_} {shop[_]["Type"]}\n### --Cost: {shop[_]["Cost"]}\n### --{shop[_]["Description"]}\n### --Buy it using `!shop buy {_}`\n'
    text += '\n## See Other Pages with `!shop page {page}`\n'
    avatar = ctx.author.avatar.url if ctx.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    embed = discord.Embed(
        title=f"{ctx.author.display_name} Shop",
        description=text,
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=avatar)
    await ctx.send(embed=embed)

def generate_content_with_retry(model, content, max_retries=5, delay=5):
    retry_count = 0
    while retry_count < max_retries:
        try:
            # The actual API call
            response = model.generate_content(content)
            return response
        except exceptions.InternalServerError as e:
            print(f"Internal Server Error (500) encountered: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
            retry_count += 1
        except Exception as e:
            # Catch other potential errors like network issues
            print(f"An unexpected error occurred: {e}")
            raise

    raise exceptions.InternalServerError("500 Internal error encountered after multiple retries.")

@bot.command()
async def roast(ctx, member: discord.Member, *, contex = ''):

    if not get_user_settings(member.id)["roast_toggle"]:
        await ctx.send(f"{member.display_name} have roasts disabled")
        return
    invoker = ctx.author
    if member.bot:
        await ctx.send(f"{member.mention} is a bot. I dont roast my own kind")
        return
    await ctx.send('This is slow, so wait')
    try:
        # Get the avatar URL. Handle cases where the member doesn't have a custom avatar.
        avatar_url = member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        # Download the image content
        image_bytes = await fetch_image(avatar_url)

        # Get the MIME type dynamically
        mime_type = get_mime_type_from_url(avatar_url)

        # Build the prompt for the model
        loop = asyncio.get_event_loop()

        prompt = (
            f"You are the best roast bot in the world. A Discord user named \"{ctx.author.display_name}\" asked if you can roast \"{member.display_name}\" "
            f"\"{member.display_name}\" has given you permission to roast them based on their avatar and context as hard as you possibly can. "
            f"{'Use as much profanity as you want ' if get_user_settings(member.id)['roast/compliment profanity'] else 'Make sure not to use ANY profanity'} "
            f"Roast intensity is set to {get_user_settings(member.id)['roast intensity']}. "
            f"The higher the number, the more intense, creative, and savage the roast should be. "
            f"The lower the number, the more it sounds like it was written from a first grader, so insults \"poopy head\" for example and just, bad insults in general"
            f"They gave you permission to roast anything about them "
            f"Make the roast at least 750 characters long"
            f"Make the roast as devastating as you can"
            f"{f' {ctx.author.display_name} added context: {contex}.' if contex else ''}"
        )

        # Call the generate_content method with a list of parts.
        # This is the corrected line.
        response = await loop.run_in_executor(
            None,  # Use default executor
            lambda: generate_content_with_retry(model, prompt),
        )

        if response.text.count(f"<@{member.id}>") > 3 or "@everyone" in response or "@here" in response:
            await ctx.send(
                f"⚠️ {ctx.author.mention}, shrine protocol triggered. Roast request denied due to spam intent.")
            try:
                end = datetime.now() + timedelta(minutes=15)
                add_punishment(invoker, "mute", datetime.now().isoformat(timespec='seconds'),end.isoformat(timespec='seconds'), "Spam Ping Attempt")

                await invoker.timeout(timedelta(minutes=15), reason="Spam roast attempt")
                await ctx.send(f"⚠️ {invoker.mention} Has beem MUTED (fucking loser)")
            except discord.Forbidden:
                await ctx.send("⚠️ I don’t have permission to mute this user.")
            except discord.HTTPException as e:
                await ctx.send(f"⚠️ Mute failed: {e}")
            return

        embed = discord.Embed(
            title=f"Roast Target: {member.display_name}",
            description=f"{member.mention} has been chosen for emotional combustion 🔥",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=avatar_url)  # Shows profile picture
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

        roast_text = response.text
        chunks = chunkify_text(roast_text,1900)

        await ctx.send(f"{member.mention} 🔥 {chunks[0]}")
        for chunk in chunks[1:]:
            await ctx.send(chunk)

    except Exception as e:
        error_text = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        user = await bot.fetch_user(1406075868786196591)
        chunks = chunkify_text(error_text, 1900)
        await user.send(f'Yo blake we got a roast flop\n\n')
        for chunk in chunks:
            await user.send(f'```{chunk}``')
        await ctx.send("Sorry there was an error. The dev of the bot has been dm abt the issue.")

@bot.command()
async def roast_img(ctx, *, contex = ''):
    member = ctx.author
    if not get_user_settings(ctx.author.id)["roast_toggle"]:
        await ctx.send(f"{ctx.author.mention} have roasts disabled")
        return
    try:
        attachments = ctx.message.attachments
        if not attachments[0].filename.split('.')[-1] in ('png','jpeg','jpg','gif','webp','avif'):
            await ctx.send('Hey idiot, your dumbass sent a file that isnt a img :wilted_rose:')
            return
    except:
        await ctx.send('There was a error with the attachment')
        return

    invoker = ctx.author

    await ctx.send('This is slow, so wait')
    try:
        avatar_url = attachments[0].url

        # Download the image content
        image_bytes = requests.get(avatar_url).content

        # Get the MIME type dynamically
        mime_type = get_mime_type_from_url(avatar_url)

        loop = asyncio.get_event_loop()
        prompt = (
            f"You are the best roast bot in the world. A Discord user named \"{ctx.author.display_name}\" "
            f"has given you a image to roast "
            f"{'Use as much profanity as you want ' if get_user_settings(ctx.author.id)['roast/compliment profanity'] else 'Make sure not to use ANY profanity'} "
            f"Roast intensity is set to {get_user_settings(member.id)['roast intensity']}. "
            f"The higher the number, the more intense, creative, and savage the roast should be. "
            f"The lower the number, the more it sounds like it was written from a first grader, so insults \"poopy head\" for example and just, bad insults in general"
            f"Roast on anything you see about the image "
            f"{f' They added context: {contex}.' if contex else ''}"
        )
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                contents=[
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_bytes}}
                ]
            )
        )
        if response.text.count(f"<@{invoker.id}>") > 3 or "@everyone" in response or "@here" in response:
            await ctx.send(
                f"⚠️ {ctx.author.mention}, shrine protocol triggered. Roast request denied due to spam intent.")
            try:
                end = datetime.now() + timedelta(minutes=15)
                add_punishment(invoker, "mute", datetime.now().isoformat(timespec='seconds'),
                               end.isoformat(timespec='seconds'), "Spam Ping Attempt")

                await invoker.timeout(timedelta(minutes=15), reason="Spam roast attempt")
                await ctx.send(f"⚠️ {invoker.mention} Has beem MUTED (fucking loser)")
            except discord.Forbidden:
                await ctx.send("⚠️ I don’t have permission to mute this user.")
            except discord.HTTPException as e:
                await ctx.send(f"⚠️ Mute failed: {e}")
            return

        embed = discord.Embed(
            title=f"Roast Target: {attachments[0].filename}",
            description=f"{ctx.author.mention} has chose to roast a pic",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=attachments[0].url)  # Shows profile picture
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

        roast_text = response.text
        chunks = chunkify_text(roast_text,1900)

        await ctx.send(f"{ctx.author.mention} 🔥 {chunks[0]}")
        for chunk in chunks[1:]:
            await ctx.send(chunk)

    except Exception as e:
        error_text = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        user = await bot.fetch_user(1406075868786196591)
        chunks = chunkify_text(error_text, 1900)
        await user.send(f'Yo blake we got a roast flop\n\n')
        for chunk in chunks:
            await user.send(f'```{chunk}``')
        await ctx.send("Sorry there was an error. The dev of the bot has been dm abt the issue.")

@bot.command()
async def compliment(ctx, member: discord.Member, *, contex = ''):
    if not get_user_settings(member.id)["compliment_toggle"]:
        await ctx.send(f"{member.display_name} have compliments disabled")
        return
    invoker = ctx.author
    if member.bot:
        await ctx.send(f"{member.mention} is a bot. I dont roast my own kind")
        return
    await ctx.send('This is slow, so wait')
    try:
        # Get the avatar URL. Handle cases where the member doesn't have a custom avatar.
        avatar_url = member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        # Download the image content
        image_bytes = await fetch_image(avatar_url)

        # Get the MIME type dynamically
        mime_type = get_mime_type_from_url(avatar_url)

        # Build the prompt for the model
        loop = asyncio.get_event_loop()
        prompt = (
            f"You are the best compliment bot in the world. A Discord user named \"{ctx.author.display_name}\" asked if you can compliment \"{member.display_name}\" "
            f"\"{member.display_name}\" has given you permission to compliment them based on their avatar and context as hard as you possibly can. "
            f"{'Use as much profanity as you want ' if get_user_settings(member.id)['roast/compliment profanity'] else 'Make sure not to use ANY profanity'} "
            f"Make them look like the best person on earth "
            f"Compliment intensity is set to {get_user_settings(member.id)['compliment intensity']}. "
            f"The higher the number, the more intense, creative, and savage the compliment should be. "
            f"The lower the number, the more it sounds like it was written from a first grader, so compliment \"pretty\" for example and just, bad compliment in general"
            f"They gave you permission to compliment anything about them "
            f"Make the compliment at least 750 characters long"
            f"compliment on anything you see that is good "
            f"{f' {ctx.author.display_name} added context: {contex}.' if contex else ''}"
        )

        # Call the generate_content method with a list of parts.
        # This is the corrected line.
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                contents=[
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_bytes}}
                ]
            )
        )

        if response.text.count(f"<@{member.id}>") > 3 or "@everyone" in response or "@here" in response:
            await ctx.send(
                f"⚠️ {ctx.author.mention}, shrine protocol triggered. Roast request denied due to spam intent.")
            try:
                end = datetime.now() + timedelta(minutes=15)
                add_punishment(invoker, "mute", datetime.now().isoformat(timespec='seconds'),
                               end.isoformat(timespec='seconds'), "Spam Ping Attempt")

                await invoker.timeout(timedelta(minutes=15), reason="Spam roast attempt")
                await ctx.send(f"⚠️ {invoker.mention} Has beem MUTED (fucking loser)")
            except discord.Forbidden:
                await ctx.send("⚠️ I don’t have permission to mute this user.")
            except discord.HTTPException as e:
                await ctx.send(f"⚠️ Mute failed: {e}")
            return

        embed = discord.Embed(
            title=f"compliment Target: {member.display_name}",
            description=f"{member.mention} has been chosen for emotional recover 🔥",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=avatar_url)  # Shows profile picture
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

        roast_text = response.text
        chunks = chunkify_text(roast_text,1900)

        await ctx.send(f"{member.mention} 🔥 {chunks[0]}")
        for chunk in chunks[1:]:
            await ctx.send(chunk)


    except Exception as e:
        user = await bot.fetch_user(1406075868786196591)
        await user.send(f'Yo blake we got a roast flop\n\n{e}')
        await ctx.send("Sorry there was a error, we pinged the developer of the bot, they will fix it soon")

@bot.command()
async def compliment_img(ctx, *, contex = ''):
    member = ctx.author
    if not get_user_settings(ctx.author.id)["compliment_toggle"]:
        await ctx.send(f"{ctx.author.mention} have compliments disabled")
        return
    try:
        attachments = ctx.message.attachments
        if not attachments[0].filename.split('.')[-1] in ('png','jpeg','jpg','gif','webp','avif'):
            await ctx.send('Hey idiot, your dumbass sent a file that isnt a img :wilted_rose:')
            return
    except:
        await ctx.send('There was a error with the attachment')
        return

    invoker = ctx.author

    await ctx.send('This is slow, so wait')
    try:
        avatar_url = attachments[0].url

        # Download the image content
        image_bytes = requests.get(avatar_url).content

        # Get the MIME type dynamically
        mime_type = get_mime_type_from_url(avatar_url)

        loop = asyncio.get_event_loop()
        prompt = (
            f"You are the best compliment bot in the world. A Discord user named \"{ctx.author.display_name}\" "
            f"has given you a image to compliment "
            f"{'Use as much profanity as you want ' if get_user_settings(ctx.author.id)['roast/compliment profanity'] else 'Make sure not to use ANY profanity'} "
            f"Make the compliment nice, clever and unforgettable."
            f"Compliment intensity is set to {get_user_settings(member.id)['compliment intensity']}. "
            f"The higher the number, the more intense, creative, and savage the compliment should be. "
            f"The lower the number, the more it sounds like it was written from a first grader, so compliment \"pretty\" for example and just, bad compliment in general"            f"compliment on anything you see about the image that is good "
            f"{f' They added context: {contex}.' if contex else ''}"
        )
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                contents=[
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_bytes}}
                ]
            )
        )
        if response.text.count(f"<@{invoker.id}>") > 3 or "@everyone" in response or "@here" in response:
            await ctx.send(
                f"⚠️ {ctx.author.mention}, shrine protocol triggered. Roast request denied due to spam intent.")
            try:
                end = datetime.now() + timedelta(minutes=15)
                add_punishment(invoker, "mute", datetime.now().isoformat(timespec='seconds'),
                               end.isoformat(timespec='seconds'), "Spam Ping Attempt")

                await invoker.timeout(timedelta(minutes=15), reason="Spam roast attempt")
                await ctx.send(f"⚠️ {invoker.mention} Has beem MUTED (fucking loser)")
            except discord.Forbidden:
                await ctx.send("⚠️ I don’t have permission to mute this user.")
            except discord.HTTPException as e:
                await ctx.send(f"⚠️ Mute failed: {e}")
            return

        embed = discord.Embed(
            title=f"Compliment Target: {attachments[0].filename}",
            description=f"{ctx.author.mention} has chose to compliment a pic",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=attachments[0].url)  # Shows profile picture
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

        roast_text = response.text
        chunks = chunkify_text(roast_text,1900)

        await ctx.send(f"{ctx.author.mention} 🔥 {chunks[0]}")
        for chunk in chunks[1:]:
            await ctx.send(chunk)


    except Exception as e:
        user = await bot.fetch_user(1406075868786196591)
        await user.send(f'Yo blake we got a image roast flop\n\n{e}')
        await ctx.send("Sorry there was a error, we pinged the developer of the bot, they will fix it soon")

@bot.command()
async def info(ctx):
    await ctx.send(f"{ctx.author.mention}\nItch.io page https://xblake-2012x.itch.io/mineflat-2d-indev\nWindows Download:https://drive.google.com/file/d/1ztycGYNl0BJWJdEDdXLAYDDGbqNOzudc/view?usp=sharing\nLinux Download:https://drive.google.com/file/d/1023v3RnWaP3yJx4Jn6LYRTwFe6zXvcLL/view?usp=sharing")

def update_user_setting(user_id, setting_key, new_value):
    file_path = f"settings/{user_id}.json"

    # Load existing settings
    with open(file_path, "r") as f:
        settings = json.load(f)

    # Update the specific setting
    settings[setting_key] = new_value

    # Save it back
    with open(file_path, "w") as f:
        json.dump(settings, f, indent=4)

def get_user_settings(user_id):
    if not os.path.exists(f'settings/{user_id}.json'):
        with open(f'settings/{user_id}.json','w') as f:
            json.dump(default_settings, f, indent=4)
    with open(f'settings/{user_id}.json','r') as f:
        user_settings = json.load(f)
    return user_settings

class Settings(View):
    def __init__(self, user: discord.User, server=1411439308778246297, settings=None):
        super().__init__(timeout=300)
        self.user_id = user.id if isinstance(user, discord.User) else user
        self.user = bot.get_user(self.user_id)
        self.guild = server
        self.settings = settings or get_user_settings(self.user_id)

        self.green = discord.ButtonStyle.green
        self.red = discord.ButtonStyle.red

    def format_settings_message(self):
        """Returns a formatted string of current settings."""
        return (
            "**MineFlat Bot Settings**\n"
            f"🔧 Roast Toggled: `{self.settings.get('roast_toggle')}`\n"
            f"💬 Compliments Toggled: `{self.settings.get('compliment_toggle')}`\n"
            f"🧨 Profanity Enabled: `{self.settings.get('roast/compliment profanity')}`\n"
            f"🔥 Roast Intensity: `{self.settings.get('roast intensity')}`\n"
            f"🌸 Compliment Intensity: `{self.settings.get('compliment intensity')}`"
        )

    def get_color(self,setting):
        self.settings = get_user_settings(self.user_id)
        if self.settings[setting] == False:
            return self.red
        else:
            return self.green

    async def update_setting(self, interaction: discord.Interaction, key: str, label: str):
        """Toggles a boolean setting."""
        new_value = not self.settings.get(key)
        update_user_setting(self.user_id, key, new_value)
        self.settings = get_user_settings(self.user_id)

        await interaction.response.send_message(
            f"✅ `{label}` toggled to `{new_value}`", ephemeral=True
        )
        await self.user.send(self.format_settings_message(), view=Settings(self.user, self.guild, self.settings))

    async def update_setting_custom_str(self, interaction: discord.Interaction, key: str, label: str, value: str):
        """Updates a string/intensity setting."""
        update_user_setting(self.user_id, key, value)
        self.settings = get_user_settings(self.user_id)

        await interaction.response.send_message(
            f"✅ `{label}` updated to `{value}`", ephemeral=True
        )
        await self.user.send(self.format_settings_message(), view=Settings(self.user, self.guild, self.settings))

    async def prompt_for_intensity(self, interaction: discord.Interaction, key: str, label: str):
        """Prompts user via DM for a new intensity value."""
        def check(msg):
            return msg.author.id == self.user_id and isinstance(msg.channel, discord.DMChannel)

        try:
            await self.user.send(f"📥 Send a new value for `{label}` (must be a number):")
            msg = await bot.wait_for("message", timeout=60.0, check=check)

            if safe_int(msg.content) is None:
                await self.user.send("❌ That’s not a number. Try again later. :wilted_rose:")
                return

            await self.update_setting_custom_str(interaction, key, label, msg.content)
        except asyncio.TimeoutError:
            await self.user.send("⌛ No response received. Setting unchanged.")

    # 🔘 Buttons
    @discord.ui.button(label="Toggle Roasting", style=discord.ButtonStyle.green)
    async def toggle_roast(self, interaction: discord.Interaction, button: Button):
        await self.update_setting(interaction, "roast_toggle", "Roasting")

    @discord.ui.button(label="Toggle Compliments", style=discord.ButtonStyle.green)
    async def toggle_compliment(self, interaction: discord.Interaction, button: Button):
        await self.update_setting(interaction, "compliment_toggle", "Compliments")

    @discord.ui.button(label="Toggle Profanity", style=discord.ButtonStyle.green)
    async def toggle_profanity(self, interaction: discord.Interaction, button: Button):
        await self.update_setting(interaction, "roast/compliment profanity", "Profanity")

    @discord.ui.button(label="Set Roast Intensity", style=discord.ButtonStyle.green)
    async def roast_intensity(self, interaction: discord.Interaction, button: Button):
        await self.prompt_for_intensity(interaction, "roast intensity", "Roast Intensity")

    @discord.ui.button(label="Set Compliment Intensity", style=discord.ButtonStyle.green)
    async def compliment_intensity(self, interaction: discord.Interaction, button: Button):
        await self.prompt_for_intensity(interaction, "compliment intensity", "Compliment Intensity")



@bot.command()
async def settings(ctx):
    user = bot.get_user(ctx.author.id)
    user_id = ctx.author.id
    setting = get_user_settings(user_id)

    view = Settings(user_id, 1411439308778246297, setting)
    await user.send(
            content=view.format_settings_message(),
            view=view)

@bot.command()
async def promo(ctx, server_name, invite_link: str, * , server_description):
    if not ctx.channel.id == 1414084660434305116:
        channel = bot.get_channel(1414084660434305116)
        await ctx.message.delete()
        await ctx.channel.send(f"{ctx.author.mention} The !promo command is to be used only in {channel.mention}")
        return

    try:
        if invite_link.startswith('https://'):
            invite_prompt = f'The server\'s invite link is {invite_link}'
        else:
            invite_prompt = f'The server\'s invite link is https://discord.gg/{invite_link}'

        invite_code = invite_link.split('/')[-1]
        url = f"https://discord.com/api/v10/invites/{invite_code}?with_counts=true&with_expiration=true"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    guild = data.get("guild", {})
                    guild_id = guild.get("id",'')
                    icon = guild.get("icon")
                    icon_url = f'https://cdn.discordapp.com/icons/{guild_id}/{icon}.png'
                else:
                    user = await bot.fetch_user(1406075868786196591)
                    await user.send(f'Yo blake we got a promo flop\n\nStatus: {response.status}')
                    await ctx.send("Sorry, there was an error. We pinged the developer of the bot—they’ll fix it soon.")
                    return

    except Exception as e:
        user = await bot.fetch_user(1406075868786196591)
        await user.send(f'Yo blake we got a promo flop\n\nError: {e}')
        await ctx.send("Sorry, there was an error. We pinged the developer of the bot—they’ll fix it soon.")
        return
    server_name = server_name.replace('_',' ')
    try:
        img_url = icon_url

        # Download the image content
        image_bytes = requests.get(img_url).content

        # Get the MIME type dynamically
        mime_type = get_mime_type_from_url(img_url)

        loop = asyncio.get_event_loop()
        await ctx.send('This take a bit')
        prompt = (
            f'Someone asked if you can make a promotion message for a server called \"{server_name}\"'
            f'They added description of the server witch is \"{server_description}\"'
            f'The attachment they sent is the cover image for the server'
            f'{invite_prompt}'
            f'They will pay you $100 to make a promo message for discord'
            f'Never go above 2000 characters'
            f'Dont add tags (#discord, #example, ect)'
            f'Please dont explain why it works, just give them the promo'
        )
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                contents=[
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_bytes}}
                ]
            )
        )
        roast_text = response.text
        chunks = chunkify_text(roast_text,1900)

        await ctx.send(f"{chunks[0]}")
        for chunk in chunks[1:]:
            await ctx.send(chunk)
        await ctx.send(f"{ctx.author.mention} Your promo for `{server_name}` is done")
    except Exception as e:
        user = await bot.fetch_user(1406075868786196591)
        await user.send(f'Yo blake we got a promo flop\n\n{e}')
        await ctx.send("Sorry there was a error, we pinged the developer of the bot, they will fix it soon")

@bot.command()
async def dad_joke(ctx):
    loop = asyncio.get_event_loop()
    await ctx.send('This take a bit')
    prompt = (
        'Say a dad joke, for example \"what do you call a cow during a earth quake? A milk shake!\" or \"Why don\'t skeletons fight each other? They dont have guts\"'
    )
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(
            contents=[
                {"text": prompt}
            ]
        )
    )
    roast_text = response.text
    chunks = chunkify_text(roast_text, 1900)

    await ctx.send(f"{ctx.author.mention}\n{chunks[0]}")
    for chunk in chunks[1:]:
        await ctx.send(chunk)

@bot.command()
async def advice(ctx, item, * , description):
    if not ctx.channel.id == 1414782375447232563:
        channel = bot.get_channel(1414782375447232563)
        await ctx.message.delete()
        await ctx.channel.send(f"{ctx.author.mention} The !advice command is to be used only in {channel.mention}")
        return

    item = item.replace('_',' ')
    try:

        loop = asyncio.get_event_loop()
        await ctx.send('This take a bit')
        prompt = (
            f'{ctx.author.display_name} Asked for advice for {item}'
            f'They described what they need help with is {description}'
            f'They would appreciate it alot if you help them'
        )
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                contents=[
                    {"text": prompt},
                ]
            )
        )
        roast_text = response.text
        chunks = chunkify_text(roast_text,1900)

        await ctx.send(f"{chunks[0]}")
        for chunk in chunks[1:]:
            await ctx.send(chunk)
        await ctx.send(f"{ctx.author.mention} Your advice for `{item}` is done")
    except Exception as e:
        user = await bot.fetch_user(1406075868786196591)
        await user.send(f'Yo blake we got a promo flop\n\n{e}')
        await ctx.send("Sorry there was a error, we pinged the developer of the bot, they will fix it soon")

@bot.command()
async def my_info(ctx, *, extra = ''):
    if extra == 'punishment history':
        with open("punishment_logs.json",'r') as f:
            logs = json.load(f)
        user_logs = logs[f'{ctx.author.id}']
        show = ''
        for _ in reversed(list(user_logs)):
            for __ in user_logs[_]:
                iso_time_start = user_logs[_][__]["start"]
                dt_start = datetime.fromisoformat(iso_time_start)
                formatted_start = dt_start.strftime("%-m/%-d/%y %-I:%M %p")
                iso_time_end = user_logs[_][__]["end"]
                dt_end = datetime.fromisoformat(iso_time_end)
                formatted_end = dt_end.strftime("%-m/%-d/%y %-I:%M %p")
                reason = user_logs[_][__]["reason"]
                show += f'\n\n{__}\n----start {formatted_start}\n----end {formatted_end}\n----reason {reason}'
        player = ctx.author
        player_avatar = player.avatar.url if player.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        embed = discord.Embed(
            title=f"{player.display_name}'s Punishment History",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=player_avatar)  # Shows profile picture
        await ctx.send(f'{ctx.author.mention}',embed=embed)
    elif extra == 'user info':
        user = ctx.author
        user_id = ctx.author.id
        user_name = ctx.author.name
        user_display_name = ctx.author.display_name
        roles = user.roles
        status = user.status
        activity = user.activity
        user_avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        show = f'Display Name : {user_display_name}\nUser Name : {user_name}\nRoles\n'
        for _ in roles:
            if _.name != "@everyone":
                show += f'---- {_.mention}\n'
        show += f'Status : {status}\nActivity : {activity}\nUser ID : {user_id}'

        embed = discord.Embed(
            title=f"{user.display_name}'s Info",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user_avatar)  # Shows profile picture
        await ctx.send(f'{ctx.author.mention}',embed=embed)
    elif extra == 'server info':
        user = ctx.author
        user_join = user.joined_at.strftime("%-m/%-d/%y %I:%M %p")
        days_in_server = (datetime.now(timezone.utc) - user.joined_at).days
        user_avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        show = f'Join Date : {user_join}\nDays In Server : {days_in_server}'


        embed = discord.Embed(
            title=f"{user.display_name}'s Server Info",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user_avatar)  # Shows profile picture
        await ctx.send(f'{ctx.author.mention}', embed=embed)
    else:
        show = (
            "**!my_info help**\n"
            "🔹 `!my_info punishment history` — Shows your punishment history\n"
            "🔹 `!my_info user info` — Shows info abt your profile\n"
            "🔹 `!my_info server info` — Shows info abt your profile on the server"
        )

        user = ctx.author
        user_avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"


        embed = discord.Embed(
            title=f"Help",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user_avatar)  # Shows profile picture
        await ctx.send(f'{ctx.author.mention}', embed=embed)

async def check_staff(ctx):
    staff_role = discord.utils.get(ctx.guild.roles, id=1419812775969947688)

    if not staff_role:
        await ctx.send("Staff role not found 💀")
        return

    member = ctx.author

    # Get the highest role the member has
    highest = member.top_role

    if highest.position >= staff_role.position:
        return True
    else:
        return False


@bot.command()
async def user_info(ctx, target, *, extra = ''):

    staff = await check_staff(ctx)
    if not staff:
        await ctx.reply("You need to be staff to use this command")
        return

    if target.startswith("<@") and target.endswith(">"):
        try:
            user_id = int(target.strip("<@!>"))
            member = ctx.guild.get_member(user_id)
        except ValueError:
            pass

    elif target.isdigit():
        member = ctx.guild.get_member(int(target))

    else:
        await ctx.reply("Please enter an valid member")
        return

    if extra == 'punishment history':
        with open("punishment_logs.json",'r') as f:
            logs = json.load(f)
        user_logs = logs[f'{member.id}']
        show = ''
        for _ in reversed(list(user_logs)):
            for __ in user_logs[_]:
                iso_time_start = user_logs[_][__]["start"]
                dt_start = datetime.fromisoformat(iso_time_start)
                formatted_start = dt_start.strftime("%-m/%-d/%y %-I:%M %p")
                iso_time_end = user_logs[_][__]["end"]
                dt_end = datetime.fromisoformat(iso_time_end)
                formatted_end = dt_end.strftime("%-m/%-d/%y %-I:%M %p")
                reason = user_logs[_][__]["reason"]
                show += f'\n\n{__}\n----start {formatted_start}\n----end {formatted_end}\n----reason {reason}'
        player = member
        player_avatar = player.avatar.url if player.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        embed = discord.Embed(
            title=f"{player.display_name}'s Punishment History",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=player_avatar)  # Shows profile picture
        await ctx.send(f'{member.mention}',embed=embed)
    elif extra == 'user info':
        user = member
        user_id = member.id
        user_name = member.name
        user_display_name = member.display_name
        roles = user.roles
        status = user.status
        activity = user.activity
        user_avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        show = f'Display Name : {user_display_name}\nUser Name : {user_name}\nRoles\n'
        for _ in roles:
            if _.name != "@everyone":
                show += f'---- {_.mention}\n'
        show += f'Status : {status}\nActivity : {activity}\nUser ID : {user_id}'

        embed = discord.Embed(
            title=f"{user.display_name}'s Info",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user_avatar)  # Shows profile picture
        await ctx.send(f'{member.mention}',embed=embed)
    elif extra == 'server info':
        user = member
        user_join = user.joined_at.strftime("%-m/%-d/%y %I:%M %p")
        days_in_server = (datetime.now(timezone.utc) - user.joined_at).days
        user_avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        show = f'Join Date : {user_join}\nDays In Server : {days_in_server}'


        embed = discord.Embed(
            title=f"{user.display_name}'s Server Info",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user_avatar)  # Shows profile picture
        await ctx.send(f'{ctx.author.mention}', embed=embed)
    else:
        show = (
            "**!user_info help**\n"
            "🔹 `!user_info punishment history` — Shows your punishment history\n"
            "🔹 `!user_info user info` — Shows info abt your profile\n"
            "🔹 `!user_info server info` — Shows info abt your profile on the server"
        )

        user = ctx.author
        user_avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"


        embed = discord.Embed(
            title=f"Help",
            description=f"{show}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user_avatar)  # Shows profile picture
        await ctx.send(f'{ctx.author.mention}', embed=embed)

def get_player_inv(user_id):
    with open(f'RPG/{user_id}/inventory.json') as f:
        inv = json.load(f)
    return inv

def get_player_stats(user_id):
    with open(f'RPG/{user_id}/stats.json') as f:
        stat = json.load(f)
    return stat

def update_player_stats(user_id,stats):
    # Save updated data back to JSON
    with open(f'RPG/{user_id}/stats.json', 'w') as f:
        json.dump(stats, f, indent=4)

def all_items():
    with open(f'RPG/items.json') as f:
        stat = json.load(f)
    return stat

def random_item_chance():
    items = all_items()
    item_name = random.choice(list(items.keys()))
    item_data = items[item_name]

    rarity = int(item_data["rarity"])

    return item_name,item_data,rarity

def add_item(user_id,item):
    with open(f'RPG/{user_id}/inventory.json','r') as f:
        data = json.load(f)

    with open(f'RPG/items.json','r') as f:
        items = json.load(f)

    if item not in data:
        data[item] = items.get(item)
    else:
        data[item] = int(data[item]) + 1

    with open(f'RPG/{user_id}/inventory.json','w') as f:
        json.dump(data, f, indent=4)

@bot.command()
async def inventory(ctx):
    inv = get_player_inv(ctx.author.id)
    inv_display = ''
    for _ in inv:
        inv_display += f'{_} : {inv.get(_,0)}\n'
    player = ctx.author
    player_avatar = player.avatar.url if player.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    embed = discord.Embed(
        title=f"{player.display_name}'s Inventory",
        description=f"{inv_display}",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=player_avatar)  # Shows profile picture
    await ctx.send(f'{ctx.author.mention}',embed=embed)

@bot.command()
async def stats(ctx):
    stat = get_player_stats(ctx.author.id)
    stat_display = ''
    for _ in stat:
        stat_display += f'{_} : {stat.get(_, 0)}\n'
    player = ctx.author
    player_avatar = player.avatar.url if player.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    embed = discord.Embed(
        title=f"{player.display_name}'s Stats",
        description=f"{stat_display}",
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=player_avatar)  # Shows profile picture
    embed.set_footer(text=f"")
    await ctx.send(f'{ctx.author.mention}', embed=embed)

places = ['bar','home','school','playground','mcdonalds','mineflat','Aussss\'s house']

class Search(View):
    def __init__(self, user: int, server=1411439308778246297):
        super().__init__(timeout=300)
        self.user_id = user
        self.user = bot.get_user(self.user_id)
        self.guild = server
        self.settings = settings
        self.channel = bot.get_channel(1414270694308446229)

        self.places = [random.choice(places) for _ in range(3)]

        for i, label in enumerate(self.places):
            self.add_item(self.make_button(label, i))

    def make_button(self, label, index):
        button = Button(label=label, style=discord.ButtonStyle.green, custom_id=f"place_{index}")

        async def callback(interaction: discord.Interaction):
            item_name, item_data, rarity = random_item_chance()
            if random.randint(1, 100) < rarity:
                await self.channel.send(f'{self.user.mention}, you got a {item_name}')
                add_item(self.user_id, item_name)
            else:
                await self.channel.send(f'{self.user.mention}, you didn\'t get anything')

            for child in self.children:
                if isinstance(child, Button):
                    child.disabled = True
            await interaction.response.edit_message(view=self)

        button.callback = callback
        return button



@bot.command()
async def search(ctx):
    player = ctx.author
    player_avatar = player.avatar.url if player.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    view = Search(player.id, 1411439308778246297)
    await ctx.send(
            f'{player.mention}',
            view=view)

class Battle(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)

        self.stats = get_player_stats(user_id)
        self.player = bot.get_user(user_id)
        self.player_avatar = self.player.avatar.url

        self.stat_display = f'HP : {self.stats["HP"]}\nDefence : {self.stats["defence"]}'

        self.embed = discord.Embed(
        title=f"{self.player.display_name}'s Stats",
        description=f"{self.stat_display}",
        color=discord.Color.red()
    )
        self.embed.set_thumbnail(url=self.player_avatar)  # Shows profile picture
        self.embed.set_footer(text=f"")

        self.opponent_stats = {"HP":100,"defence":0}

        self.stat_display = f'HP : {self.opponent_stats["HP"]}\nDefence : {self.opponent_stats["defence"]}'

        self.embed1 = discord.Embed(
            title=f"Opponent's Stats",
            description=f"{self.stat_display}",
            color=discord.Color.red()
        )
        self.embed1.set_thumbnail(url=self.player_avatar)  # Shows profile picture
        self.embed1.set_footer(text=f"")

        self.add_item(self.make_button("Attack", 0))
        self.add_item(self.make_button("Items", 1))
        self.add_item(self.make_button("Flee", 2))

    async def on_timeout(self):
        # Optional: refresh embeds one last time
        self.refresh_embeds()

        # Optional: disable buttons
        for item in self.children:
            item.disabled = True

        # Optional: send a final message or edit the existing one
        if hasattr(self, "message"):
            await self.message.edit(
                content="⏳ The battle has timed out.",
                embeds=[self.embed, self.embed1],
                view=self
            )

    async def init_display(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def update_display(self):
        await self.message.edit(embeds=[self.embed, self.embed1], view=self)

    class Player:
        def __init__(self, user_id):
            self.user_id = user_id
            self.stats = get_player_stats(user_id)

        def damage(self,dmg):
            self.stats['HP'] -= int(dmg) if not safe_int(dmg) is None else 0

            update_player_stats(self.user_id,self.stats)

    def damage(self,dmg):
        self.opponent_stats["HP"] -= int(dmg) if not safe_int(dmg) is None else 0

    def refresh_embeds(self):
        # Update player stats
        self.stat_display = f'HP : {self.stats["HP"]}\nDefence : {self.stats["defence"]}'
        self.embed.description = self.stat_display

        # Update opponent stats
        opponent_display = f'HP : {self.opponent_stats["HP"]}\nDefence : {self.opponent_stats["defence"]}'
        self.embed1.description = opponent_display

    def make_button(self, label, index):
        button = Button(label=str(label), style=discord.ButtonStyle.green, custom_id=f"{index}")
        async def callback(interaction: discord.Interaction):
            if index == 0:
                self.damage(10)
            if index == 1:
                self.player_obj = self.Player(self.player.id)
                self.player_obj.damage(10)
                self.stats = get_player_stats(self.player.id)
            if index == 2:
                pass

            self.refresh_embeds()

            await interaction.response.edit_message(view=self,embeds=[self.embed,self.embed1])

        button.callback = callback
        return button


@bot.command()
async def battle(ctx):
    player = ctx.author
    view = Battle(player.id)

    # Send initial message with placeholder embeds
    message = await ctx.send(
        f'{player.mention}',
        embeds=[view.embed, view.embed1],
        view=view
    )

    # If you want to edit the message later, store it in the class
    view.message = message

class ApplicationStartView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="📬 Apply Now", style=discord.ButtonStyle.primary)
    async def start_application(self, interaction: discord.Interaction, button: ui.Button):
        await apply(interaction)  # Reuse your existing command logic

class ReviewView(ui.View):
    def __init__(self, applicant: discord.User):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.message = None  # Will be set after sending

    @ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DecisionModal("Accepted", self.applicant, self))

    @ui.button(label="❌ Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DecisionModal("Denied", self.applicant, self))

class DecisionModal(ui.Modal):
    def __init__(self, decision: str, applicant: discord.User, review_view: ReviewView):
        super().__init__(title=f"{decision} Application",timeout=None)
        self.decision = decision
        self.applicant = applicant
        self.review_view = review_view
        self.reason = ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        def __init__(self):
            super().__init__(timeout=None)
        log_channel = interaction.guild.get_channel(1419820503211835483)

        embed = discord.Embed(
            title=f"Application {self.decision}",
            description=f"**Applicant:** {self.applicant.mention}\n**Reviewed by:** {interaction.user.mention}",
            color=discord.Color.green() if self.decision == "Accepted" else discord.Color.red()
        )
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        embed.set_footer(text=f"User ID: {self.applicant.id}")

        await log_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Application {self.decision} and logged.", ephemeral=True)

        # Disable buttons
        for child in self.review_view.children:
            child.disabled = True
        await self.review_view.message.edit(view=self.review_view)

        # DM applicant
        try:
            dm = await self.applicant.create_dm()
            await dm.send(f"📬 Your application was **{self.decision}**.\n**Reason:** {self.reason.value}")
        except:
            await interaction.followup.send("❌ Could not DM the applicant.", ephemeral=True)

async def apply(interaction: discord.Interaction):
    channel = interaction.channel
    await interaction.response.send_message("📬 Check your DMs to begin your application!", ephemeral=True)
    await start_application_flow(interaction)

async def start_application_flow(interaction: discord.Interaction):
    try:
        dm = await interaction.user.create_dm()
        await dm.send("Welcome to the staff application! Please answer the following questions one by one.")

        def check(m):
            return m.author == interaction.user and m.channel == dm

        questions = [
            ("Your Name", "What's your real or preferred name?"),
            ("Your Age", "How old are you?"),
            ("Staff Experience", "Have you been staff before? If yes, where and what role?"),
            ("Leave Reason", "If you left, why?"),
            ("Weaknesses", "What are your weaknesses?"),
            ("Strengths", "What are your strengths?"),
            ("Role", "What role are you applying for?"),
            ("Why Fit", "Why do you think you're a good fit for this role?"),
            ("Spam Response", "If someone spammed (3+ msgs in 5 sec), what would you do?")
        ]

        responses = {}

        for key, question in questions:
            await dm.send(f"**{question}**")
            msg = await interaction.client.wait_for("message", check=check, timeout=300)
            responses[key] = msg.content

        embed = discord.Embed(title="New Application Submitted", color=discord.Color.green())
        embed.set_author(name=f"{interaction.user.name}#{interaction.user.discriminator}", icon_url=interaction.user.avatar.url if interaction.user.avatar.url else "https://cdn.discordapp.com/embed/avatars/0.png")

        for key, answer in responses.items():
            embed.add_field(name=key, value=answer, inline=False)

        embed.set_footer(text=f"User ID: {interaction.user.id}")

        review_view = ReviewView(interaction.user)
        message = await interaction.guild.get_channel(APPLICATION_CHANNEL_ID).send(embed=embed, view=review_view)
        review_view.message = message

        await dm.send("✅ Your application has been submitted!")

    except Exception as e:
        await interaction.user.send("❌ Something went wrong or you took too long. Please try again.")
        print(f"Application error: {e}")


@bot.command()
async def application_panel(ctx):
    guild = ctx.guild
    user = ctx.author
    mod_role_id = 1419812775969947688  # Replace with your actual mod role ID

    mod_role = guild.get_role(mod_role_id)
    user_top_role = user.top_role

    await ctx.message.delete()

    # Check if user has mod role or a role higher in hierarchy
    if user_top_role < mod_role:
        await ctx.send("❌ You don’t have permission to use this command.")
        return

    embed = discord.Embed(
        title="📜 Staff Applications",
        description="Click the button below to begin your application.",
        color=discord.Color.blurple()
    )
    view = ApplicationStartView()
    await ctx.send(embed=embed, view=view)

block_default = [
    {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0},
    {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0},
    {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0},
    {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0},
    {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0},
    {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0}
]

default_block = {'Block': 'None', "Stage": 0,'Upgrades': [''],"MoneyStored": 0}

block_incomes = {}
with open('Block Tycoon/Shop/incomes') as f:
    for line in f.readlines():
        block = line.split(':')[0]
        income = line.split(':')[1]
        block_incomes[block] = int(income)

block_upgrades = {}
with open('Block Tycoon/Shop/upgrades') as f:
    for line in f.readlines():
        name = line.split(':')[0]
        multiplier = line.split(':')[1]
        block_upgrades[name] = int(multiplier)

block_emojis = {}
with open('Block Tycoon/Shop/BlockEmojis') as f:
    for line in f.readlines():
        name = line.split(':')[1].replace('\n','')
        emojis = line.split(':')[0]
        block_emojis[name] = emojis

def calculate_income(user_id,block_number):
    try:
        blocks = block_stats(user_id)['Blocks']
        block = blocks[int(block_number)]
        stage = block['Stage']
        base_income = int(block_incomes[block['Block']])
        multiplier = 1
        for _ in block['Upgrades']:
            try:
                multiplier += int(block_upgrades[_])
            except Exception as e:
                pass
        power = stage - 1
        return base_income * (2 ** power) * multiplier
    except Exception as e:
        return 0

def block_stats(user_id):
    user_id = str(user_id)
    data_path = f'Block Tycoon/players/{user_id}'
    json_path = f'{data_path}/stats.json'
    if not os.path.exists(data_path):
        os.mkdir(data_path)

        default = {
            "Blocks": block_default,
            "Cash": 50,
            "Inventory": {}
        }

        with open(json_path,'w') as f:
            json.dump(default,f,indent = 4)
    with open(json_path) as f:
        return json.load(f)

def block_change_stat(user_id, stat, to):
    stats = block_stats(user_id)
    stats[stat] = to
    data_path = f'Block Tycoon/players/{user_id}'
    json_path = f'{data_path}/stats.json'
    with open(json_path, 'w') as f:
        json.dump(stats,f,indent=4)

def suffix(n):
    return suffix_number(n)

shop_items = {}
with open('Block Tycoon/Shop/items') as f:
    for line in f.readlines():
        block = line.split(':')[0]
        cost = line.split(':')[1]
        shop_items[block] = int(cost)

class BlockSelect(Select):
    def __init__(self, inventory, number):
        options = [
            discord.SelectOption(label=block, description=f"Quantity: {count}")
            for block, count in inventory.items()
        ]
        self.number = number
        super().__init__(placeholder="Choose a block to place", options=options)

    async def callback(self, interaction):
        chosen_block = self.values[0]
        user_id = str(interaction.user.id)
        stats = block_stats(user_id)
        inventory = stats['Inventory']
        blocks = stats['Blocks']

        if inventory[chosen_block] <= 0:
            await interaction.response.send_message(f"You don’t have any {chosen_block} to place.", ephemeral=True)
            return

        # Consume block from inventory
        inventory[chosen_block] -= 1
        if inventory[chosen_block] == 0:
            del inventory[chosen_block]

        # Replace slot
        upgrades = ''
        if 'cursed_' in chosen_block:
            chosen_block = chosen_block.replace('cursed_','')
            upgrades = 'cursed'
        elif 'rainbow_' in chosen_block:
            chosen_block = chosen_block.replace('rainbow_', '')
            upgrades = 'rainbow'

        if not blocks[self.number]['Block'] == 'None':
            await interaction.response.send_message(f'There is already a block at slot {self.number}')
            return

        blocks[self.number] = {
            'Block': chosen_block,
            'Stage': 1,
            'Upgrades': [upgrades],
            'MoneyStored': 0
        }

        block_change_stat(user_id, 'Inventory', inventory)
        block_change_stat(user_id, 'Blocks', blocks)

        await interaction.response.send_message(f"Successfully placed one {chosen_block} block in Slot {self.number}.")

class UpgradeBlockSelect(Select):
    def __init__(self, inventory: dict):
        options = []
        for raw, qty in inventory.items():
            base = raw.split('_', 1)[-1]
            if raw.startswith("rainbow_"):
                label = f"🌈 {base}"
            elif raw.startswith("cursed_"):
                label = f"💀 {base}"
            else:
                label = base

            options.append(discord.SelectOption(
                label=label, description=f"Qty: {qty}", value=raw
            ))

        super().__init__(
            placeholder="Select block to upgrade",
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        user_id  = str(interaction.user.id)
        stats    = block_stats(user_id)
        inv      = stats.setdefault('Inventory', {})
        raw      = self.values[0]
        base     = raw.split('_', 1)[-1]
        count    = inv.get(raw, 0)

        if raw.startswith("rainbow_"):
            return await interaction.response.send_message(
                "Already 🌈 Rainbow.", ephemeral=True
            )

        # Set rates and caps
        if raw.startswith("cursed_"):
            rate, cap, target = 0.25, 4, f"rainbow_{base}"
        else:
            rate, cap, target = 0.20, 5, f"cursed_{base}"

        max_amount = min(cap, count)
        if max_amount < 1:
            return await interaction.response.send_message(
                f"You need at least one `{base}`.", ephemeral=True
            )

        modal = Modal(title=f"Sacrifice 1–{max_amount} `{base}`")
        placeholder = (
            f"1={rate*100:.0f}% → "
            f"{max_amount}={min(max_amount*rate*100,100):.0f}%"
        )
        modal.add_item(TextInput(
            label="Number of blocks",
            placeholder=placeholder,
            required=True,
            max_length=2
        ))

        async def on_submit(inner: discord.Interaction):
            try:
                amt = int(modal.children[0].value)
            except ValueError:
                return await inner.response.send_message(
                    "Not a valid number.", ephemeral=True
                )

            if not 1 <= amt <= max_amount:
                return await inner.response.send_message(
                    f"Enter 1–{max_amount}.", ephemeral=True
                )

            inv[raw] -= amt
            if inv[raw] <= 0:
                inv.pop(raw)

            chance = min(amt * rate, 1.0)
            if random.random() < chance:
                inv[target] = inv.get(target, 0) + 1
                result = (
                    f"✅ Success! `{base}` → `{target}` "
                    f"({chance*100:.0f}% chance)"
                )
            else:
                result = f"❌ Failed ({chance*100:.0f}% chance)."

            block_change_stat(user_id, 'Inventory', inv)
            await inner.response.send_message(result)

        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

class UpgradeView(View):
    def __init__(self, inventory: dict):
        super().__init__(timeout=60)
        self.add_item(UpgradeBlockSelect(inventory))

async def block_upgrade(ctx):
    user_id   = str(ctx.author.id)
    stats     = block_stats(user_id)
    inventory = stats.get('Inventory', {})

    if not inventory:
        return await ctx.reply("Your inventory is empty.", ephemeral=True)

    await ctx.reply("Select a block to upgrade:", view=UpgradeView(inventory), ephemeral=True)

async def block_place(ctx, number: int):
    stats = block_stats(str(ctx.author.id))
    inventory = stats['Inventory']

    if not inventory:
        await ctx.reply("Your inventory is empty.")
        return

    if number > 6 or 0 > number:
        embed = discord.Embed(
            title=f"Invalid Number",
            description=f"{number} is invalid, choose from 0-5",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
        return
    embed = discord.Embed(
        title=f"Placing at Slot {number}",
        description="Choose a block to place:",
        color=discord.Color.green()
    )

    view = View()
    view.add_item(BlockSelect(inventory,number))
    await ctx.reply(embed=embed, view=view)

@tasks.loop(seconds=1)
async def income_players(dir = 'Block Tycoon/players/'):
    for name in os.listdir(dir):
        full_path = os.path.join(dir, name)
        if os.path.isdir(full_path):
            user_id = name
            stats = block_stats(user_id)
            blocks = stats['Blocks']
            for i, block in enumerate(blocks):
                block_name = block['Block']
                money = calculate_income(user_id,i)
                stored = block['MoneyStored']
                block['MoneyStored'] = stored + money
                blocks[i] = block
            block_change_stat(user_id,'Blocks',blocks)

async def skillbar(ctx):
    bar_length = 7
    target_index = random.randint(0,bar_length - 1)
    pos = 0
    direction = 1
    stopped = False
    loop = asyncio.get_event_loop()
    result_future = loop.create_future()  # 🔑 store result here

    def make_bar():
        bar = []
        for i in range(bar_length):
            if i == pos:
                bar.append("▒")
            elif i == target_index:
                bar.append("🎯")
            else:
                bar.append("⬜")
        return "[" + "".join(bar) + "]"

    embed = discord.Embed(
        title="⚒️ Forge Upgrade",
        description="Stop the bar on 🎯 to stack!",
        color=0xffd700
    )
    embed.add_field(name="Bar", value=make_bar())

    view = discord.ui.View()

    async def stop_callback(interaction: discord.Interaction):
        nonlocal stopped
        stopped = True
        if pos == target_index:
            await interaction.response.edit_message(
                embed=discord.Embed(title="✅ Success!", description="You stacked 1 block", color=0x00ff00),
                view=None
            )
            result_future.set_result(True)
        else:
            await interaction.response.edit_message(
                embed=discord.Embed(title="❌ Failure!", description="You lost 1 block", color=0xff0000),
                view=None
            )
            result_future.set_result(False)

    button = discord.ui.Button(label="STOP", style=discord.ButtonStyle.primary)
    button.callback = stop_callback
    view.add_item(button)

    msg = await ctx.send(embed=embed, view=view)

    while not stopped:
        await asyncio.sleep(0.4)
        pos += direction
        if pos == bar_length - 1 or pos == 0:
            direction *= -1

        embed = discord.Embed(title="Block Stack",
                              description="Stop the bar on 🎯 to stack!",
                              color=0xffd700)
        embed.add_field(name="Bar", value=make_bar())
        await msg.edit(embed=embed, view=view)

    return await result_future  # 🔑 return True/False to caller


valid_commands = ['view','view blocks','view inventory','shop','place','collect','upgrade','pickup','stack']
command_help = {
    'view': 'Show you your blocks and their stats',
    'view blocks': 'Show you your blocks and their stats',
    'view inventory': 'Show you your inventory',
    'shop': 'Look in the shop',
    'place': 'Place down a block',
    'collect': "Collect money from your blocks",
    'upgrade': "Upgrade your blocks",
    'pickup': "Pick up a block off your plot into your inventory",
    'stack': "Stack your block to double the income"
}

@bot.command()
async def block(ctx, action = 'None', block_number = None):
    if ctx.channel.id != 1422308849452580976:
        await ctx.reply(f'Use this channel in {bot.get_channel(1422308849452580976).mention}')
        return
    user_id = str(ctx.author.id)
    stats = block_stats(user_id)
    if block_number is not None:
        block_number = str(block_number).lower()
    if action.lower() not in valid_commands:
        valid = ''
        for _ in valid_commands:
            valid += f'\n`{_}` - {command_help[_]}'

        await ctx.reply(f'`{action}` is not a valid command\nValid commands are\n{valid}')
        return

    if action.lower() == 'view':
        if block_number == 'blocks' or block_number is None:
            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Blocks",
                description="Your current block stats:",
                color=discord.Color.gold()
            )
            blocks = stats['Blocks']
            for i, block_data in enumerate(blocks):
                block_type = block_data['Block']
                stage = block_data['Stage']
                income = calculate_income(user_id, i)  # still works if calculate_income uses index
                upgrades = ', '.join(block_data.get('Upgrades', [])) or 'None'
                stored = block_data.get('MoneyStored', 0)

                embed.add_field(
                    name=f"{block_type}{block_emojis[block_type]} (Slot {i})",
                    value=f"Stage: {stage}\nIncome: ${suffix(income)}\nStored: ${suffix(stored)}\nUpgrades: {upgrades}",
                    inline=True
                )

            await ctx.reply(embed=embed)

        elif block_number == 'inventory':
            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Inventory",
                description="Your current inventory:",
                color=discord.Color.gold()
            )
            inventory = stats['Inventory']
            for block_type, count in inventory.items():
                embed.add_field(name=f'{block_type}{block_emojis[block_type]}', value=f"Quantity: {count}",
                                inline=True)

            await ctx.reply(embed=embed)

    if action.lower() == 'shop':
        if block_number is None:
            embed = discord.Embed(
                title=f"Shop",
                description=f"Your current money is ${suffix(stats['Cash'])}",
                color=discord.Color.gold()
            )
            for i,(block, cost) in enumerate(shop_items.items()):
                embed.add_field(name=f'{block}{block_emojis[block]}', value=f"Cost: {suffix(cost)}\nBuy with !block shop {i}", inline=True)

            await ctx.reply(embed=embed)
        else:
            if 0 > int(block_number) or int(block_number) > len(shop_items.items()) - 1:
                await ctx.reply(f'{block_number} is not a valid block number, choose from 0 to {len(shop_items.items()) - 1}')
                return

            block = list(shop_items.items())[int(block_number)]
            name = block[0]
            cost = block[1]
            cash = stats['Cash']
            inventory = stats['Inventory']

            if cash < cost:
                await ctx.reply(f'You don\'t have enough cash for {name}\nYou need ${suffix(cost)}You have ${suffix(cash)}')
                return

            block_change_stat(user_id,'Cash',int(cash) - int(cost))
            if name in inventory:
                amount = int(inventory[name]) + 1
            else:
                amount = 1

            inventory[name] = amount
            block_change_stat(user_id, 'Inventory', inventory)

            await ctx.reply(f'Successfully bought {name} for ${cost}')

    if action.lower() == 'place':
        if safe_int(block_number) is None:
            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Blocks",
                description="Your current block stats:",
                color=discord.Color.gold()
            )
            blocks = stats['Blocks']
            for i, block_data in enumerate(blocks):
                block_type = block_data['Block']
                stage = block_data['Stage']
                income = calculate_income(user_id, i)  # still works if calculate_income uses index
                upgrades = ', '.join(block_data.get('Upgrades', [])) or 'None'
                stored = block_data.get('MoneyStored', 0)

                embed.add_field(
                    name=f"{block_type}{block_emojis[block_type]} (Slot {i})",
                    value=f"Stage: {stage}\nIncome: ${suffix(income)}\nStored: ${suffix(stored)}\nUpgrades: {upgrades}",
                    inline=True
                )

            await ctx.reply(embed=embed)
        else:
            await block_place(ctx,int(block_number))

    if action.lower() == 'collect':
        if safe_int(block_number) is None and not block_number == 'all':
            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Blocks",
                description="Your current block stats:",
                color=discord.Color.gold()
            )
            blocks = stats['Blocks']
            for i, block_data in enumerate(blocks):
                block_type = block_data['Block']
                stage = block_data['Stage']
                income = calculate_income(user_id, i)  # still works if calculate_income uses index
                upgrades = ', '.join(block_data.get('Upgrades', [])) or 'None'
                stored = block_data.get('MoneyStored', 0)

                embed.add_field(
                    name=f"{block_type}{block_emojis[block_type]} (Slot {i})",
                    value=f"Stage: {stage}\nIncome: ${suffix(income)}\nStored: ${suffix(stored)}\nUpgrades: {upgrades}",
                    inline=True
                )
            embed.add_field(name='Choose a block number money to collect with !block collect {number}',value='or type !block collect all to collect all', inline=True)

            await ctx.reply(embed=embed)
        else:
            if block_number == 'all':
                embed = discord.Embed(
                    title=f"{ctx.author.display_name} Collected",
                    description="You collected:",
                    color=discord.Color.gold()
                )
                blocks = stats['Blocks']
                current = stats['Cash']
                total = 0
                for i, block_data in enumerate(blocks):
                    block_type = block_data['Block']
                    cash = block_data["MoneyStored"]
                    blocks[i]["MoneyStored"] = 0
                    embed.add_field(name=f'{block_type}{block_emojis[block_type]} (Slot {i})',
                                    value=f"${suffix(cash)}", inline=True)
                    total += cash
                embed.add_field(name='For a total amount of',value=f'${suffix(total)}',inline=True)
                block_change_stat(user_id,'Blocks',blocks)
                block_change_stat(user_id, 'Cash', current + total)

                await ctx.reply(embed=embed)
            else:
                block_number = int(block_number)
                if block_number > 5 or block_number < 0:
                    await ctx.reply(f'{block_number} is a invalid slot, valid slots are 0-5')
                    return
                embed = discord.Embed(
                    title=f"{ctx.author.display_name} Collected",
                    description="You collected:",
                    color=discord.Color.gold()
                )
                blocks = stats['Blocks']
                current = stats['Cash']
                total = 0
                block = blocks[block_number]
                block_type = block['Block']
                cash = block["MoneyStored"]
                blocks[block_number]["MoneyStored"] = 0
                embed.add_field(name=f'{block_type}{block_emojis[block_type]} (Slot {block_number})',
                                value=f"${suffix(cash)}", inline=True)
                total += cash
                embed.add_field(name='For a total amount of',value=f'${suffix(total)}',inline=True)
                block_change_stat(user_id,'Blocks',blocks)
                block_change_stat(user_id, 'Cash', current + total)

                await ctx.reply(embed=embed)

    if action.lower() == 'upgrade':
        await block_upgrade(ctx)

    if action.lower() == 'pickup':
        if safe_int(block_number) is None:
            await ctx.reply(f'{block_number} isn\'t a valid slot number, valid slot numbers are 0-5')
            return
        block_number = int(block_number)
        if block_number > 5 or block_number < 0:
            await ctx.reply(f'{block_number} isn\'t a valid slot number, valid slot numbers are 0-5')
            return
        blocks = stats['Blocks']
        inventory = stats['Inventory']
        block = blocks[block_number]
        blocks[block_number] = default_block
        if 'cursed' in block['Upgrades']:
            add = f'cursed_{block["Block"]}'
        elif 'rainbow' in block['Upgrades']:
            add = f'rainbow_{block["Block"]}'
        else:
            add = block['Block']

        if add in inventory:
            amount = inventory[add] + 1
        else:
            amount = 1

        inventory[add] = amount

        block_change_stat(user_id,'Blocks',blocks)
        block_change_stat(user_id,'Inventory',inventory)

    if action.lower() == 'stack':
        if safe_int(block_number) is None:
            await ctx.reply(f'{block_number} isn\'t a valid slot number, valid slot numbers are 0-5')
            return
        block_number = int(block_number)
        if block_number > 5 or block_number < 0:
            await ctx.reply(f'{block_number} isn\'t a valid slot number, valid slot numbers are 0-5')
            return
        blocks = stats['Blocks']
        block = blocks[block_number]
        block_name = block["Block"]
        if block_name == 'None':
            await ctx.reply(f'This block isn\'t upgradeable')
            return
        stage = block["Stage"]
        if stage >= 20:
            await ctx.reply('This block is already maxed')
            return
        outcome = await skillbar(ctx)
        if outcome:
            blocks[block_number]['Stage'] = blocks[block_number]['Stage'] + 1
        else:
            if not blocks[block_number]['Stage'] <= 1:
                blocks[block_number]['Stage'] = blocks[block_number]['Stage'] - 1
        block_change_stat(user_id,'Blocks',blocks)

def parse_duration_2(duration_str):
    if duration_str.endswith("h"):
        start = float(duration_str[:-1]) * 60
        return start * 60
    elif duration_str.endswith("m"):
        return float(duration_str[:-1]) * 60
    elif duration_str.endswith("s"):
        return float(duration_str[:-1])

class PollButton(Button):
    def __init__(self, label, poll_view):
        super().__init__(label=f'{label}: 0 votes', custom_id=label)
        self.poll_view = poll_view
        self.custom_id = label

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id in self.poll_view.voters:
            await interaction.response.send_message("You already voted!", ephemeral=True)
            return
        self.poll_view.voters.add(interaction.user.id)
        self.poll_view.picked[self.poll_view.options.index(self.custom_id)] += 1
        self.label = f"{self.custom_id}: {self.poll_view.picked[self.poll_view.options.index(self.custom_id)]} votes"
        await interaction.response.send_message(f"You voted: {self.custom_id}", ephemeral=True)
        await self.poll_view.button_pressed()

class PollUIOng(View):
    def __init__(self, options, duration, delete_after_ending):
        super().__init__(timeout=parse_duration_2(duration))
        self.options = options
        self.picked = [0 for _ in options]
        self.message = None  # Will be set later
        self.voters = set()
        self.delete_after_ending = delete_after_ending

        for option in options:
            self.add_item(PollButton(option, self))

    async def button_pressed(self):
        await self.message.edit(view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            # Find the winning option
            max_index = self.picked.index(max(self.picked))
            winner = self.options[max_index]
            results = "\n".join(
                f"{opt}: {count} vote{'s' if count != 1 else ''}"
                for opt, count in zip(self.options, self.picked)
            )
            await self.message.reply(f"{POLL_ROLE.mention}\n⏰ Poll ended! Winner is **{winner}**\n\n{results}")

            if self.delete_after_ending:
                await self.message.delete()

@bot.command()
async def poll(ctx, poll_question, poll_end_time, poll_answers, delete_after_ending: bool = False):
    try:
        if len(poll_answers) < 2:
            await ctx.send("Please provide at least two options separated by `--`.")
            return
        view = PollUIOng(poll_answers.split('--'), poll_end_time, delete_after_ending)

        duration_seconds = parse_duration_2(poll_end_time)
        duration = timedelta(seconds=duration_seconds)
        end_timestamp = discord.utils.utcnow() + duration
        formatted_time = discord.utils.format_dt(end_timestamp, style='R')  # Shows "in 24 hours"
        poll_text = f"{POLL_ROLE.mention}\n\"{poll_question}\" 🕒 Ends {formatted_time}"

        sent_msg = await ctx.send(poll_text,view=view)
        view.message = sent_msg
        await ctx.message.delete()
    except Exception as e:
        await ctx.send(e)

bot.run("Token")
