import os
from dotenv import load_dotenv
import cv2
import discord
from discord.ext import commands
import numpy as np
from io import BytesIO
from te4stats import processStats


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')


def convertImage(img, name):
    imgEncode = cv2.imencode('.jpg', img)[1]
    byteEncode = np.array(imgEncode).tobytes()
    byteImage = BytesIO(byteEncode)
    f = discord.File(byteImage, filename=name)
    return f


@discord.app_commands.allowed_installs(guilds=True, users=True)
@discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="getstats", description="get te4 stats (arg specifies number of matches to attach as images)")
async def getstats(interaction: discord.Interaction, arg: int=1):
    await interaction.response.defer()
    stats, lastMatchStats, matchPlot = processStats(arg)
    files=[]
    for i, img in enumerate(lastMatchStats, 1):
        files.append(convertImage(img, f'lastMatchStats{i}.jpg'))
    files.append(convertImage(matchPlot, "matchPlot.jpg"))

    await interaction.followup.send(content=stats, files=files)


if __name__ == "__main__":
    load_dotenv()
    bot.run(os.getenv("DISCORD_API"))