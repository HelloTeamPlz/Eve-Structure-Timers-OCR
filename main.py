import asyncio
import discord
from discord.ext import commands, tasks
import os
from structure_timers import StructureBot as sb
from PIL import Image
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.environ.get("discbot")
timer_response_channel = int(os.environ.get("channel_id"))

TIMERS_FILE = "timers.txt"
TIMER_MESSAGE_ID_FILE = "timer_message_id.txt"

timer_dict_glob = {}
timer_message_id = None

timer_message_ids = {
    "red": None,
    "green": None,
    "blue": None,
}

timer_lock = asyncio.Lock()

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


def save_timer_message_id(message_id=None):
    with open(TIMER_MESSAGE_ID_FILE, "w") as file:
        for key, value in timer_message_ids.items():
            if value:
                file.write(f"{key}={value}\n")


def load_timer_message_id():
    global timer_message_id

    try:
        with open(TIMER_MESSAGE_ID_FILE, "r") as file:
            content = file.read().strip()

        if not content:
            return

        if "=" in content:
            for line in content.splitlines():
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key, value = parts
                    if key in timer_message_ids:
                        timer_message_ids[key] = int(value)
        else:
            old_message_id = int(content)
            timer_message_id = old_message_id
            timer_message_ids["red"] = old_message_id

    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Could not load timer message ID: {e}")


def get_old_timers(file_path):
    now = sb.unix_time_now()

    try:
        with open(file_path, "r") as file:
            for line in file:
                parts = line.strip().split(":", 1)

                if len(parts) == 2:
                    ts = int(parts[0])
                    name = parts[1]

                    if ts + 3600 > now:
                        timer_dict_glob[ts] = name

    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Could not load old timers: {e}")


def build_timer_embed(title, lines, color):
    description = "\n".join(lines)

    if not description:
        description = "No timers in this category."

    if len(description) > 4000:
        description = description[:3900] + "\n\nToo many timers to show."

    return discord.Embed(
        title=title,
        description=description,
        color=color
    )


async def send_or_edit_timer_embed(channel, key, embed):
    msg_id = timer_message_ids.get(key)
    msg = None

    if msg_id is not None:
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            timer_message_ids[key] = None
        except discord.HTTPException as e:
            print(f"Could not fetch {key} timer message: {e}")
            timer_message_ids[key] = None

    if msg is not None:
        try:
            await msg.edit(content=None, embed=embed)
            save_timer_message_id()
            return
        except discord.NotFound:
            timer_message_ids[key] = None
        except discord.Forbidden:
            print(f"Bot does not have permission to edit {key} timer message.")
            return
        except discord.HTTPException as e:
            print(f"Could not edit {key} timer message: {e}")
            timer_message_ids[key] = None

    new_msg = await channel.send(embed=embed)
    timer_message_ids[key] = new_msg.id
    save_timer_message_id()


async def update_timer_message():
    async with timer_lock:
        response_channel = bot.get_channel(timer_response_channel)

        if response_channel is None:
            response_channel = await bot.fetch_channel(timer_response_channel)

        sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))

        txt_msg = "\n".join(
            [f"{key}:{value}" for key, value in sorted_timers.items()]
        )
        sb.write_to_timers_txt(txt_msg)

        now = sb.unix_time_now()

        red_lines = []
        green_lines = []
        blue_lines = []

        for key, value in sorted(timer_dict_glob.items(), reverse=True):
            seconds_left = key - now

            if seconds_left <= 0:
                continue

            line = f"{value} <t:{key}:f> <t:{key}:R> ID: {key}"

            if seconds_left < 12 * 60 * 60:
                red_lines.append(line)
            elif seconds_left < 24 * 60 * 60:
                green_lines.append(line)
            else:
                blue_lines.append(line)

        red_embed = build_timer_embed(
            "Critical Timers",
            red_lines,
            discord.Color.red()
        )

        green_embed = build_timer_embed(
            "Upcoming Timers",
            green_lines,
            discord.Color.green()
        )

        blue_embed = build_timer_embed(
            "Future Timers",
            blue_lines,
            discord.Color.blue()
        )
        await send_or_edit_timer_embed(response_channel, "blue", blue_embed)
        await send_or_edit_timer_embed(response_channel, "green", green_embed)
        await send_or_edit_timer_embed(response_channel, "red", red_embed)
        


@bot.event
async def on_ready():
    print("the bot is ready")

    response_channel = bot.get_channel(timer_response_channel)

    if response_channel is None:
        response_channel = await bot.fetch_channel(timer_response_channel)

    deleted = 0

    async for msg in response_channel.history(limit=20):
        if msg.author.id == bot.user.id:
            try:
                await msg.delete()
                deleted += 1
            except Exception as e:
                print(f"Could not delete message: {e}")

            if deleted >= 10:
                break

    global timer_message_ids
    timer_message_ids = {
        "red": None,
        "green": None,
        "blue": None,
    }

    load_timer_message_id()
    get_old_timers(TIMERS_FILE)

    await update_timer_message()

    if not remove_expired_timers.is_running():
        remove_expired_timers.start()

@bot.command()
async def t(ctx, *, time):
    try:
        timers_data = sb.timer(time)
        timer_dict_glob[timers_data[1]] = timers_data[0]

        await update_timer_message()

    except Exception as e:
        print(f"t command error: {e}")
        await ctx.send("Could not add timer.", delete_after=40)


@bot.command()
async def timer(ctx, *args):
    user = ctx.message.author

    if len(ctx.message.attachments) == 0:
        await ctx.send("Please attach an image to the command.", delete_after=40)
        return

    image_url = ctx.message.attachments[0].url
    timer_args = " ".join(args)

    try:
        image = Image.open(requests.get(image_url, stream=True).raw)
        image.save("saved_image.png")

        results = sb.read_img("saved_image.png")
        parsed_datetime = sb.date_from_list(results)
        unix_ts = sb.to_unix_time(parsed_datetime)

        timer_dict_glob[unix_ts] = timer_args

        await update_timer_message()

    except Exception as e:
        print(f"timer image command error: {e}")
        await ctx.send(
            f"Cant read the date plz add manualy with !t command {user.mention}",
            delete_after=40
        )


@bot.command()
async def td(ctx, days: int, hours: int, minutes: int, *, name: str):
    try:
        delta_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)

        utc_now = datetime.now(timezone.utc)
        utc_epoch_ts = int((utc_now + timedelta(seconds=delta_seconds)).timestamp())

        timer_dict_glob[utc_epoch_ts] = name

        await update_timer_message()

    except Exception as e:
        print(f"td command error: {e}")
        await ctx.send(
            "Usage: `!td <days> <hours> <minutes> <name>`",
            delete_after=40
        )


@bot.command()
async def bulk_timer(ctx, *args):
    if len(ctx.message.attachments) == 0:
        await ctx.send("Please attach a timer file.", delete_after=40)
        return

    attachment = ctx.message.attachments[0]

    try:
        response = requests.get(attachment.url)

        if response.status_code != 200:
            await ctx.send("Could not download the timer file.", delete_after=40)
            return

        with open("bulk.txt", "wb") as file:
            file.write(response.content)

        with open("bulk.txt", "r") as file:
            for line in file:
                parts = line.strip().split(":", 1)

                if len(parts) == 2:
                    timer_dict_glob[int(parts[0])] = parts[1]

        await update_timer_message()
        await ctx.send("adding timers", delete_after=20)

    except Exception as e:
        print(f"Bulk timer error: {e}")
        await ctx.send("add it the hard way", delete_after=40)


@bot.command(aliases=["remove", "delete"])
async def rem(ctx, key):
    try:
        key = int(key)
    except ValueError:
        await ctx.send("Timer ID must be a number.", delete_after=20)
        return

    if key in timer_dict_glob:
        del timer_dict_glob[key]
        await ctx.send(f'Timer with key "{key}" has been removed.', delete_after=20)
        await update_timer_message()
    else:
        await ctx.send(f'Timer with key "{key}" not found.', delete_after=20)


@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear_timers(ctx):
    timer_dict_glob.clear()

    await update_timer_message()
    await ctx.send("All timers cleared.", delete_after=20)


@tasks.loop(seconds=5)
async def remove_expired_timers():
    current_unix_time = sb.unix_time_now()

    keys_to_remove = [
        key for key in list(timer_dict_glob.keys())
        if key + 3600 < current_unix_time
    ]

    for key in keys_to_remove:
        timer_dict_glob.pop(key, None)

    await update_timer_message()


@remove_expired_timers.error
async def remove_expired_timers_error(error):
    print(f"remove_expired_timers error: {error}")

@bot.command()
async def export_timers(ctx):
    now = sb.unix_time_now()

    active_timers = {
        key: value
        for key, value in sorted(timer_dict_glob.items())
        if key + 3600 > now
    }

    if not active_timers:
        await ctx.send("No active timers to export.", delete_after=30)
        return

    export_text = "\n".join(
        [f"{key}:{value}" for key, value in active_timers.items()]
    )

    if len(export_text) <= 1900:
        await ctx.send(f"```text\n{export_text}\n```")
    else:
        chunks = []
        current_chunk = ""

        for line in export_text.splitlines():
            if len(current_chunk) + len(line) + 1 > 1800:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += f"\n{line}" if current_chunk else line

        if current_chunk:
            chunks.append(current_chunk)

        for chunk in chunks:
            await ctx.send(f"```text\n{chunk}\n```")    


def main():
    if not api_key:
        raise RuntimeError("Missing Discord bot token. Check your .env file.")

    bot.run(api_key)


if __name__ == "__main__":
    main()