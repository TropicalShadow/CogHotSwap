from discord.ext.commands import Cog
from discord.ext import commands

class basic_cog(Cog):
    def __init__(self,bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping_command(self,ctx,*args,**kwargs):
        await ctx.send("pong")

def setup(bot):
    bot.add_cog(basic_cog(bot))