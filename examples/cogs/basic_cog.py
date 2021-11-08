from discord.ext.commands import Cog
from discord.ext import commands

class basic_cog(Cog):
    def __init__(self,bot):
        self.bot = bot

    @commands.command(name="showcogs")
    async def ping_command(self,ctx,*args):
        """General Command, 
        To see that the command are reloaded change a value and run the command again
        """
        self.bot.watcher.show_cogs()# Throws information into console about the cogs.
        await ctx.send("bonk")

    @Cog.listener()
    async def on_ready(self):
        """This will only run once on_ready... if you want it to trigger again you will need
        to reload your bot or if you know what you are doing you could use dispatch()
        """
        print("Bot loaded")

def setup(bot):
    bot.add_cog(basic_cog(bot))