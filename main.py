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

timer_dict_glob = {}
timer_message_id = None

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())


def get_old_timers(file_path):
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.strip().split(':')
                if len(parts) == 2:
                    timer_dict_glob[int(parts[0])] = parts[1]
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Could not load old timers: {e}")


async def update_timer_message():
    global timer_message_id

    response_channel = bot.get_channel(timer_response_channel)

    if response_channel is None:
        response_channel = await bot.fetch_channel(timer_response_channel)

    sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))

    txt_msg = '\n'.join(
        [f'{key}:{value}' for key, value in sorted_timers.items()]
    )
    sb.write_to_timers_txt(txt_msg)

    if sorted_timers:
        timers_msg = '\n'.join(
            [f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()]
        )
    else:
        timers_msg = "There are no active timers."

    timer_msg = None

    if timer_message_id is not None:
        try:
            timer_msg = await response_channel.fetch_message(timer_message_id)
        except discord.NotFound:
            timer_message_id = None
        except discord.HTTPException as e:
            print(f"Could not fetch timer message: {e}")
            timer_message_id = None

    if timer_msg is None:
        async for msg in response_channel.history(limit=50):
            if msg.author.id == bot.user.id:
                timer_msg = msg
                timer_message_id = msg.id
                break

    if timer_msg:
        try:
            await timer_msg.edit(content=timers_msg)
            return
        except discord.NotFound:
            timer_message_id = None
        except discord.Forbidden:
            print("Bot does not have permission to edit timer message.")
            return
        except discord.HTTPException as e:
            print(f"Could not edit timer message: {e}")
            timer_message_id = None

    new_msg = await response_channel.send(timers_msg)
    timer_message_id = new_msg.id


@bot.event
async def on_ready():
    print('the bot is ready')

    get_old_timers('timers.txt')

    await update_timer_message()

    if not remove_expired_timers.is_running():
        remove_expired_timers.start()


@bot.command()
async def t(ctx, *, time):
    timers_data = sb.timer(time)
    timer_dict_glob[timers_data[1]] = timers_data[0]

    await update_timer_message()


@bot.command()
async def timer(ctx, *args):
    user = ctx.message.author

    if len(ctx.message.attachments) == 0:
        await ctx.send("Please attach an image to the command.", delete_after=40)
        return

    image_url = ctx.message.attachments[0].url
    timer_args = ' '.join(args)

    image = Image.open(requests.get(image_url, stream=True).raw)
    image.save("saved_image.png")

    try:
        results = sb.read_img("saved_image.png")
        parsed_datetime = sb.date_from_list(results)
        unix_ts = sb.to_unix_time(parsed_datetime)

        timer_dict_glob[unix_ts] = timer_args

        await update_timer_message()

    except Exception:
        await ctx.send(
            f'Cant read the date plz add manualy with !t command {user.mention}',
            delete_after=40
        )

@bot.command()
async def td(ctx, name: str, days: int, hours: int, minutes: int):
    try:
        delta_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)

        utc_now = datetime.now(timezone.utc)
        utc_epoch_ts = int((utc_now + timedelta(seconds=delta_seconds)).timestamp())

        timer_dict_glob[utc_epoch_ts] = name

        await update_timer_message()

    except Exception as e:
        print(f"td command error: {e}")
        await ctx.send(
            'Usage: `!td <name> <days> <hours> <minutes>`',
            delete_after=40
        )

    except Exception as e:
        print(f"td command error: {e}")
        await ctx.send(
            'Usage: !td <name> <days> <hours> <minutes>',
            delete_after=40
        )

@bot.command()
async def bulk_timer(ctx, *args):
    if len(ctx.message.attachments) == 0:
        await ctx.send("Please attach an image to the command.", delete_after=40)
        return

    attachment = ctx.message.attachments[0]
    response = requests.get(attachment.url)

    if response.status_code != 200:
        await ctx.send("Could not download the timer file.", delete_after=40)
        return

    with open('bulk.txt', 'wb') as file:
        file.write(response.content)

    try:
        with open('bulk.txt', 'r') as file:
            for line in file:
                parts = line.strip().split(':')
                if len(parts) == 2:
                    timer_dict_glob[int(parts[0])] = parts[1]

        await update_timer_message()
        await ctx.send('adding timers', delete_after=20)

    except Exception as e:
        print(f"Bulk timer error: {e}")
        await ctx.send('add it the hard way', delete_after=40)


@tasks.loop(seconds=5)
async def remove_expired_timers():
    current_unix_time = sb.unix_time_now()

    # Wait 1 hour after the timer expires before removing it
    keys_to_remove = [
        key for key in list(timer_dict_glob.keys())
        if (key + 3600) < current_unix_time
    ]

    if not keys_to_remove:
        return

    for key in keys_to_remove:
        timer_dict_glob.pop(key, None)

    await update_timer_message()


@remove_expired_timers.error
async def remove_expired_timers_error(error):
    print(f"remove_expired_timers error: {error}")


@bot.command()
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


def main():
    bot.run(api_key)


if __name__ == "__main__":
    main()