import asyncio
import logging
import os
import sys
from functools import wraps
from pathlib import Path
from typing import Optional

from discord.ext import commands
from watchgod import Change, awatch


__all__ = (
    "Watcher",
    "watch",
)


class Watcher:
    """The core cogwatch class -- responsible for starting up watchers and managing cogs.
    Attributes
        :bot: A discord Bot.
        :path: Root name of the cogs directory; cogwatch will only watch within this directory -- recursively.
        :debug: Whether to run the bot only when the debug flag is True. Defaults to True.
        :loop: Custom event loop. If not specified, will use the current running event loop.
        :default_logger: Whether to use the default logger (to sys.stdout) or not. Defaults to True.
        :preload: Whether to detect and load all found cogs on startup. Defaults to False.
    """

    __slots__ = (
        "bot",
        "path",
        "debug",
        "loop",
        "default_logger",
        "preload"
    )

    def __init__(
        self,
        bot: commands.Bot,
        path: str = "commands",
        debug: bool = True,
        loop: asyncio.BaseEventLoop = None,
        default_logger: bool = True,
        preload: bool = False,
    ):
        self.bot = bot
        self.path = path
        self.debug = debug
        self.loop = loop
        self.default_logger = default_logger
        self.preload = preload

        bot.watcher = self
        bot.add_listener(self.on_ready,"on_ready")

        if default_logger:
            _default = logging.getLogger(__name__)
            _default.setLevel(logging.INFO)
            _default_handler = logging.StreamHandler(sys.stdout)
            _default_handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
            _default.addHandler(_default_handler)

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

        # iterate over the list backwards in order to get the first occurrence in cases where a duplicate
        # name exists in the path (ie. example_proj/example_proj/commands)
        try:
            root_index = rtokens.index(self.path.split("/")[0]) + 1
        except ValueError:
            raise ValueError("Use forward-slash delimiter in your `path` parameter.")

        return ".".join([token for token in tokens[-root_index:-1]])


    async def on_ready(self):
        await self.start()

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
                            await self._unload(cog_dir)
                        elif change_type == Change.added:
                            await self._load(cog_dir)
                        elif change_type == Change.modified and change_type != (Change.added or Change.deleted):
                            await self._reload(cog_dir)

            except FileNotFoundError:
                continue

            else:
                await asyncio.sleep(1)

        else:
            await self.start()

    def get_cog_dot_path(self, file_path: str):
        filename = self.get_cog_name(file_path)
        new_dir = self.get_dotted_cog_path(file_path)
        return f"{new_dir}.{filename.lower()}" if new_dir else f"{self.path}.{filename.lower()}"

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
                logging.error(f"The path {Path.cwd() / self.path} does not exist.")
                _check = True

        else:
            logging.info(f"Found {Path.cwd() / self.path}!")
            if self.preload:
                await self._preload()

            if self.check_debug():
                if self.loop is None:
                    self.loop = asyncio.get_event_loop()

                logging.info(f"Watching for file changes in {Path.cwd() / self.path}...")
                self.loop.create_task(self._start())

    async def load(self, cog_dir: str, package: Optional[str] = None):
        await self._load(self.get_cog_dot_path(cog_dir),package=package)

    async def _load(self, dot_cog_path: str, package: Optional[str] = None):
        """Loads a cog file into the bot."""
        try:
            self.bot.load_extension(dot_cog_path, package=package)
        except commands.ExtensionAlreadyLoaded:
            return
        except Exception as exc:
            self.cog_error(exc)
        else:
            logging.info(f"Cog Loaded: {dot_cog_path}")

    async def unload(self, cog_dir: str, package: Optional[str] = None):
        await self._unload(self.get_cog_dot_path(cog_dir),package=package)

    async def _unload(self, dot_cog_path: str, package: Optional[str] = None):
        """Unloads a cog file into the bot."""
        try:
            self.bot.unload_extension(dot_cog_path, package=package)
        except Exception as exc:
            self.cog_error(exc)
        else:
            logging.info(f"Cog Unloaded: {dot_cog_path}")

    async def reload(self, cog_path: str, package: Optional[str] = None):
        await self._reload(self.get_cog_dot_path(cog_path),package=package)

    async def _reload(self, dot_cog_path: str, package: Optional[str] = None):
        """Attempts to atomically reload the file into the bot."""
        try:
            self.bot.reload_extension(dot_cog_path, package=package)
        except Exception as exc:
            self.cog_error(exc)
        else:
            logging.info(f"Cog Reloaded: {dot_cog_path}")

    @staticmethod
    def cog_error(exc: Exception):
        """Logs exceptions. TODO: Need thorough exception handling."""
        if isinstance(exc, (commands.ExtensionError, SyntaxError)):
            logging.exception(exc)

    async def _preload(self):
        logging.info("Preloading...")
        for cog in {(file.stem, file) for file in Path(Path.cwd() / self.path).rglob("*.py")}:
            new_dir = self.get_dotted_cog_path(cog[1])
            await self._load(".".join([new_dir, cog[0]]))


def watch(**kwargs):
    """Instantiates a watcher by hooking into a Bot bot methods' `self` attribute."""

    def decorator(function):
        @wraps(function)
        async def wrapper(bot):
            cw = Watcher(bot,**kwargs)
            await cw.start()
            retval = await function(bot)
            return retval

        return wrapper

    return decorator