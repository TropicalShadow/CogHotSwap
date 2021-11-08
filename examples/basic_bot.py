from discord.ext.commands import Bot
from coghotswap import Watcher
from os import chdir, path

with open(".env","r") as f:
    TOKEN = f.read()

chdir(path.dirname(__file__))


bot = Bot("!")
Watcher(bot, path="cogs",preload=True,verbose=False)# all you need is to add this, and throw some arguments into the constructor

# Use the default loading and unloading 
#bot.unload_extension()
#bot.load_extension()

bot.run(TOKEN)