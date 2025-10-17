import asyncio
import time

from colorama import Style, Fore
from telethon import TelegramClient

from src.parser import load_config
from src.protector import load_symmetric_key, load_string_session
from src.core.set_config import set_config
from src.core.listing import list_pushed_files
from src.core.push import push_data
from src.core.pull import pull_data
from src.cloudmapmanager import (
    setup_cloudmap,
    check_health_cloudmap,
    clean_prepared_data,
)


async def main():
    config = load_config()

    if config.action == "config":
        set_config(config)
        return
    elif config.action == "list":
        list_pushed_files(config)
        return

    result = load_symmetric_key(config.password)
    if not result["success"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - {result['error']}{Style.RESET_ALL}"
        )
        return

    string_session = load_string_session(result["symmetric_key"])

    async with TelegramClient(
        string_session, api_id=config.api_id, api_hash=config.api_hash
    ) as client:
        if not check_health_cloudmap():
            await setup_cloudmap(
                client, string_session.save(), config.api_id, config.api_hash
            )
            return

        try:
            if config.action == "push":
                await push_data(client, result["symmetric_key"], config)

            elif config.action == "pull":
                await pull_data(client, result["symmetric_key"], config)

        except KeyboardInterrupt:
            loop = asyncio.get_running_loop()
            for task in asyncio.all_tasks(loop):
                task.cancel()

    clean_prepared_data()


if __name__ == "__main__":
    asyncio.run(main())
