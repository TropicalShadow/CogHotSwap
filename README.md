# CogHotSwap

> Work in progress

You ever wish that your discord bot cogs would just reload by themselves? Well now you can, by adding just one line of code to your bot we will automate the reloading of all your cogs, and hopefully give you feed back (Coming Soon Feature).

This project was built for [Pycord](https://github.com/Pycord-Development/pycord) a fork of [Discord.py](https://github.com/Rapptz/discord.py)

----

## Installation

```sh
git clone https://github.com/TropicalShadow/CogHotSwap
cd CogHotSwap
python -m pip install -U .
```

or if you have git, add this to your requirements.txt

```sh
git+https://github.com/TropicalShadow/CogHotSwap
```

----

## Coming Soon Features

- [x] List of unloaded cogs that can be loaded or have errored
- [x] Enchance the reloading of the files

----
Examples [here](examples/basic_bot.py)

```py
from discord.ext.commands import Bot
from coghotswap import Watcher

bot = Bot("!")
Watcher(bot, path="cogs")

bot.run("token")
```

----

## Need Support?

Contact me on discord `RealName_123#2570`
