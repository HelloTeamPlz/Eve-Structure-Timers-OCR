import discord
from discord.ext import commands, tasks
import os
from structure_timers import StructureBot as sb
from PIL import Image
import discord
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".") / ".env"

load_dotenv(dotenv_path=env_path)

#static keys
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
              timer_dict_glob.update({int(parts[0]):parts[1]})
        file.close()
  except:
    pass

@bot.event
async def on_ready():
    print('the bot is ready')

    file_path = 'timers.txt'
    get_old_timers(file_path)

    if not remove_expired_timers.is_running():
        remove_expired_timers.start()

    response_channel = bot.get_channel(timer_response_channel)

    sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))
    timers_msg = '\n'.join(
        [f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()]
    )

    await response_channel.purge(limit=5)
    await response_channel.send(timers_msg or "There are no active timers.")

@bot.command()
async def t(ctx, *, time):
    '''
    creates a timer for a structure in a specified channel
    '''
    response_channel = bot.get_channel(timer_response_channel)
    timers_data = sb.timer(time)
    timer_dict_glob.update({timers_data[1]: timers_data[0]})
    #sort the timers and retrieve from the dictionary
    sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))
    timers_msg = '\n'.join([f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()])
    txt_msg = '\n'.join([f'{key}:{value}'for key,value in sorted_timers.items()])
    sb.write_to_timers_txt(txt_msg)
    try:
      await response_channel.purge(limit=2)
      await response_channel.send(timers_msg)
    except:
      await response_channel.purge(limit=2)
      await response_channel.send(timers_msg)

@bot.command()
async def timer(ctx, *args):
  
    response_channel = bot.get_channel(timer_response_channel)
    user = ctx.message.author
  
    # Check if an image is attached to the message
    if len(ctx.message.attachments) == 0:
        await ctx.send("Please attach an image to the command.",  delete_after=40)
        return

    # Get the first attached image
    image_url = ctx.message.attachments[0].url
    timer_args = ' '.join(args)

    # Download and save the image
    image = Image.open(requests.get(image_url, stream=True).raw)
    image.save("saved_image.png")
    try:
      results = sb.read_img("saved_image.png")
      parsed_datetime = sb.date_from_list(results)
      unix_ts = sb.to_unix_time(parsed_datetime)
      timer_dict_glob.update({unix_ts: timer_args})
      try: 
        #sort the timers and retrieve from the dictionary
        sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))
        timers_msg = '\n'.join([f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()])
        txt_msg = '\n'.join([f'{key}:{value}'for key,value in sorted_timers.items()])
        sb.write_to_timers_txt(txt_msg)
        try:
          await response_channel.purge(limit=2)
          await response_channel.send(timers_msg)
        except:
          await response_channel.send(timers_msg)
      except:
        await ctx.send(results)
    except:
      await ctx.send(f'Cant read the date plz add manualy with !t command {user.mention}',delete_after=40)

@bot.command()
async def td(ctx, str_nm="", days=0, hours=0, minutes=0):
    response_channel = bot.get_channel(timer_response_channel)
    user = ctx.message.author
    try:
          # Convert days, hours, and minutes to seconds
          delta_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
          # Get the current UTC time
          utc_now = datetime.utcnow()
          # Calculate the UTC epoch timestamp by adding the delta to the current time
          utc_epoch_ts = int((utc_now + timedelta(seconds=delta_seconds)).timestamp())
          timer_dict_glob.update({utc_epoch_ts: str_nm})
          sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))
          timers_msg = '\n'.join([f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()])
          txt_msg = '\n'.join([f'{key}:{value}'for key,value in sorted_timers.items()])
          sb.write_to_timers_txt(txt_msg)
          try:
            await response_channel.purge(limit=2)
            await response_channel.send(timers_msg)
          except:
            pass

    except ValueError:
          await ctx.send(f'this command needs <structure name> <days> <hours> <minutes>{user.mention}',delete_after=40)

@bot.command()
async def bulk_timer(ctx, *args):
  
    response_channel = bot.get_channel(timer_response_channel)
    
  
    # Check if an image is attached to the message
    if len(ctx.message.attachments) == 0:
        await ctx.send("Please attach an image to the command.",  delete_after=40)
        return

    # Get the first attached image
    attachment = ctx.message.attachments[0]
    url = attachment.url
    response = requests.get(url)
    if response.status_code == 200:
      with open('bulk.txt', 'wb') as file:
          file.write(response.content)
          file.close()
    
    with open('bulk.txt', 'r') as file:
      for line in file:
        parts = line.strip().split(':')
        if len(parts) == 2:
          timer_dict_glob.update({int(parts[0]):parts[1]})
    file.close()
        
    
    #sort the timers and retrieve from the dictionary
    try: 
      sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))
      txt_msg = '\n'.join([f'{key}:{value}'for key,value in sorted_timers.items()])
      sb.write_to_timers_txt(txt_msg)
      try:
        await response_channel.purge(limit=2)
        await ctx.send('adding timers')
        #await response_channel.send(timers_msg)
      except:
        await ctx.send('adding timers', delete_after=40)
    except:
      await ctx.send('add it the hard way',delete_after=40)
      
@tasks.loop(seconds=5)
async def remove_expired_timers():
    global timer_message_id

    response_channel = bot.get_channel(timer_response_channel)

    if response_channel is None:
        response_channel = await bot.fetch_channel(timer_response_channel)

    current_unix_time = sb.unix_time_now()

    keys_to_remove = [
        key for key in list(timer_dict_glob.keys())
        if (key + 3600) < current_unix_time
    ]

    if not keys_to_remove:
        return

    for key in keys_to_remove:
        timer_dict_glob.pop(key, None)

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
            timer_msg = None
            timer_message_id = None
        except discord.HTTPException as e:
            print(f"Could not fetch saved timer message: {e}")
            timer_msg = None
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
    
@bot.command()
async def rem(ctx, key):
    key = int(key)
    response_channel = bot.get_channel(timer_response_channel)
    if key in timer_dict_glob:
        # Delete the timer associated with the given key
        del timer_dict_glob[key]
        await ctx.send(f'Timer with key "{key}" has been removed.')
        sorted_timers = dict(sorted(timer_dict_glob.items(), reverse=True))
        timers_msg = '\n'.join([f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()])
        txt_msg = '\n'.join([f'{key}:{value}'for key,value in sorted_timers.items()])
        sb.write_to_timers_txt(txt_msg)
        await response_channel.purge(limit=5)
        try: 
          await response_channel.send(timers_msg)
        except:
          await response_channel.send('There are no active timers.')
    else:
        await ctx.send(f'Timer with key "{key}" not found.')


def main():
    
    bot.run(api_key)

if __name__ == "__main__":
    main()