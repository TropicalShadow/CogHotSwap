from discord.ext.commands import Bot
from coghotswap import Watcher

bot = Bot("!")
Watcher(bot, path="cogs")

bot.start("token")