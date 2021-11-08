import asyncio
import logging
import os
import sys
from watchgod import Change, awatch
from types import FunctionType
from functools import wraps, update_wrapper
from typing import Optional
from enum import auto, Enum
from pathlib import Path

from discord.errors import ExtensionAlreadyLoaded, ExtensionError
from discord.ext import commands

__all__ = (
    "Watcher",
    "ModuleStatus"
)
def copy_func(f):
    g = FunctionType(f.__code__, f.__globals__, name=f.__name__,
                           argdefs=f.__defaults__,
                           closure=f.__closure__)
    g = update_wrapper(g, f)
    g.__kwdefaults__ = f.__kwdefaults__
    return g

class ModuleStatus(Enum):
    UNKNOWN = auto()
    UNLOADED = auto()
    LOADED = auto()
    FAILED = auto()
    
    
    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return f"<ModuleStatus.{self.name}: {self.value}>"

class Watcher:
    """The core coghotswap class -- responsible for starting up watchers and managing cogs.
    Attributes
        :bot: A discord Bot.
        :path: Root name of the cogs directory; coghotswap will only watch within this directory -- recursively.
        :debug: Whether to run the bot only when the debug flag is True. Defaults to True.
        :loop: Custom event loop. If not specified, will use the current running event loop.
        :default_logger: Whether to use the default logger (to sys.stdout) or not. Defaults to True.
        :preload: Whether to detect and load all found cogs on startup. Defaults to False.
        :verbose: Wheather to log everything that is used to help debug. Defaults to False.
    """

    __slots__ = (
        "bot",
        "path",
        "debug",
        "loop",
        "preload",
        "_cogs",
        "_logger",
        "_load_extension",
        "_unload_extension",
        "_reload_extension",
    )

    def __init__(
        self,
        bot: commands.Bot,
        path: str = "commands",
        debug: bool = True,
        loop: asyncio.BaseEventLoop = None,
        default_logger: bool = True,
        preload: bool = False,
        verbose: bool = False,
    ):
        self.bot = bot
        self.path = path
        self.debug = debug
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.preload = preload
        self._cogs = {}

        bot.watcher = self
        bot.add_listener(self.on_ready,"on_ready")
        self._load_extension = copy_func(bot.load_extension)
        self._unload_extension = copy_func(bot.unload_extension)
        self._reload_extension = copy_func(bot.reload_extension)
        bot.load_extension = self._load
        bot.unload_extension = self._unload
        bot.reload_extension = self._reload
        
        
        if(default_logger):
            self._logger = logging.getLogger(__name__)
            if(verbose):
                self._logger.setLevel(logging.DEBUG)
            else:
                self._logger.setLevel(logging.INFO)
        else:
            self._logger = logging.getLogger(None)
        _default_handler = logging.StreamHandler(sys.stdout)
        _default_handler.setFormatter(logging.Formatter("[CogHotSwap] %(message)s"))
        self._logger.addHandler(_default_handler)
        
        self.loop.create_task(self.start())        
        self._logger.info("CogHotSwap has been registered.")
    
    
    @property
    def cogs(self):
        return self._cogs
    
    def show_cogs(self):
        for cog, status in self._cogs.items():
            if(status == ModuleStatus.FAILED):
                self._logger.info(f"{cog} has {str(status).lower()}")
            else:
                self._logger.info(f"{cog} is {str(status)}")
    
    @staticmethod
    def get_cog_name(path: str) -> str:
        """Returns the cog file name without .py appended to it."""
        _path = os.path.normpath(path)
        return _path.split(os.sep)[-1:][0][:-3]

    def get_dotted_cog_path(self, path: str) -> str:
        """Returns the full dotted path that discord.py uses to load cog files."""
        _path = os.path.normpath(path)
        tokens = _path.split(os.sep)
        rtokens = list(reversed(tokens))
        
        try:
            root_index = rtokens.index(self.path.split("/")[0]) + 1
        except ValueError:
            raise ValueError("Use forward-slash delimiter in your `path` parameter.")

        return ".".join([token for token in tokens[-root_index:-1]])

    async def on_ready(self):
        for extension in self.bot.extensions:
            if(not extension in self._cogs):
                self._cogs[extension] = ModuleStatus.LOADED

    async def _start(self):
        """Starts a watcher, monitoring for any file changes and dispatching event-related methods appropriately."""
        while self.dir_exists():
            try:
                async for changes in awatch(Path.cwd() / self.path):
                    self.validate_dir()  # cannot figure out how to validate within awatch; some anomalies but it does work...

                    reverse_ordered_changes = sorted(changes, reverse=True)

                    for change in reverse_ordered_changes:
                        change_type = change[0]
                        change_path = change[1]

                        cog_dir = self.get_cog_dot_path(change_path)

                        if change_type == Change.deleted:
                            if(cog_dir in self.bot.extensions):
                                self._unload(cog_dir)
                            if(cog_dir in self._cogs):del self._cogs[cog_dir]
                        elif change_type == Change.added:
                            self._load(cog_dir)
                        elif change_type == Change.modified and change_type != (Change.added or Change.deleted):
                            if(cog_dir in self.bot.extensions):
                                self._reload(cog_dir)
                            else:
                                self._load(cog_dir)

            except FileNotFoundError:
                continue

            else:
                await asyncio.sleep(1)

        else:
            await self.start()

    def get_cog_dot_path(self, file_path: str):
        filename = self.get_cog_name(file_path)
        new_dir = self.get_dotted_cog_path(file_path)
        return f"{new_dir}.{filename}" if new_dir else f"{self.path}.{filename}"

    def check_debug(self):
        """Determines if the watcher should be added to the event loop based on debug flags."""
        return any([(self.debug and __debug__), not self.debug])

    def dir_exists(self):
        """Predicate method for checking whether the specified dir exists."""
        return Path(Path.cwd() / self.path).exists()

    def validate_dir(self):
        """Method for raising a FileNotFound error when the specified directory does not exist."""
        if not self.dir_exists():
            raise FileNotFoundError
        return True

    async def start(self):
        """Checks for a user-specified event loop to start on, otherwise uses current running loop."""
        _check = False
        while not self.dir_exists():
            if not _check:
                self._logger.error(f"The path {Path.cwd() / self.path} does not exist.")
                _check = True

        else:
            self._logger.info(f"Found {Path.cwd() / self.path}!")
            if self.preload:
                self._preload()
            self.add_unloaded_cogs()
            if self.check_debug():
                self._logger.info(f"Watching for file changes in {Path.cwd() / self.path}...")
                self.loop.create_task(self._start())

    def add_unloaded_cogs(self):
        for file in Path(Path.cwd() / self.path).rglob("*.py"):
            new_dir = self.get_dotted_cog_path(str(file))
            cog_dir = ".".join([new_dir, file.stem])
            if(not cog_dir in self._cogs):
                self._cogs[cog_dir] = ModuleStatus.UNLOADED

    def load(self, cog_dir: str):
        self._load(self.get_cog_dot_path(cog_dir))

    def _load(self, dot_cog_path: str):
        """Loads a cog file into the bot."""
        try:
            self._logger.debug(f"trying to load {dot_cog_path}")
            self._load_extension(self=self.bot,name=dot_cog_path)
        except ExtensionAlreadyLoaded:
            return self._logger.debug(f"{dot_cog_path} already loaded cog")
        except Exception as exc:
            self._cogs[dot_cog_path] = ModuleStatus.FAILED
            self.cog_error(exc)
        else:
            self._cogs[dot_cog_path] = ModuleStatus.LOADED
            self._logger.info(f"Cog Loaded: {dot_cog_path}")

    def unload(self, cog_dir: str):
        self._unload(self.get_cog_dot_path(cog_dir))

    def _unload(self, dot_cog_path: str, remove: bool = False):
        """Unloads a cog file into the bot."""
        try:
            self._logger.debug(f"trying to unload {dot_cog_path}")
            self._unload_extension(self=self.bot, name=dot_cog_path)
        except Exception as exc:
            if(remove):
                if(self._cogs[dot_cog_path]):del self._cogs[dot_cog_path]
            else:
                self._cogs[dot_cog_path] = ModuleStatus.UNKNOWN
            self.cog_error(exc)
        else:
            if(remove):
                if(self._cogs[dot_cog_path]):del self._cogs[dot_cog_path]
            else:
                self._cogs[dot_cog_path] = ModuleStatus.UNLOADED
            self._logger.info(f"Cog Unloaded: {dot_cog_path}")

    def reload(self, cog_path: str):
        self._reload(self.get_cog_dot_path(cog_path))

    def _reload(self, dot_cog_path: str):
        """Attempts to atomically reload the file into the bot."""
        try:
            self._logger.debug(f"trying to reload {dot_cog_path}")
            self._reload_extension(self=self.bot, name=dot_cog_path)
        except Exception as exc:
            self._cogs[dot_cog_path] = ModuleStatus.FAILED
            self.cog_error(exc)
        else:
            self._logger.info(f"Cog Reloaded: {dot_cog_path}")


    def cog_error(self, exc: Exception):
        """Logs exceptions. TODO: Need thorough exception handling."""
        self._logger.exception(exc)

    def _preload(self):
        self._logger.debug("Preloading...")
        for file in Path(Path.cwd() / self.path).rglob("*.py"):
            cog_name = file.stem
            file_path = str(file)
            self._logger.debug(f"Preloading {cog_name}...")
            new_dir = self.get_dotted_cog_path(file_path)
            self._load(".".join([new_dir, cog_name]))
