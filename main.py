import asyncio
import time

from colorama import Style, Fore
from telethon import TelegramClient

from src.config_manager.config_parser import parse_config
from src.protector import load_symmetric_key
from src.tl import load_string_session
from src.utils import clean_prepared_data
from src.core.config_setting import set_general_config, set_cloud_channel_config
from src.core.listing import list_pushed_files
from src.core.push import push_data
from src.core.pull import pull_data
from src.setup import setup_telecloud, check_health_cloudmap


async def main():
    if not check_health_cloudmap():
        await setup_telecloud()
        return

    config = parse_config()

    if config.command == "config":
        set_general_config(config)
        return

    # in order to create a new channel we have to act like end-user
    elif (
        config.command == "channel"
        and not config.new_cloudchannel
        and not config.deleted_cloudchannel
    ):
        await set_cloud_channel_config(config)
        return

    elif config.command == "list":
        list_pushed_files(config)
        return

    result = load_symmetric_key(config.password)
    if not result["success"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - {result['error']}{Style.RESET_ALL}"
        )
        return

    async with TelegramClient(
        load_string_session(result["symmetric_key"]),
        api_id=config.api_id,
        api_hash=config.api_hash,
    ) as client:
        try:
            if config.command == "channel":
                await set_cloud_channel_config(config, client)
                return

            elif config.command == "push":
                await push_data(client, result["symmetric_key"], config)

            elif config.command == "pull":
                await pull_data(client, result["symmetric_key"], config)

        except KeyboardInterrupt:
            loop = asyncio.get_running_loop()
            for task in asyncio.all_tasks(loop):
                task.cancel()

    clean_prepared_data(config.command)


if __name__ == "__main__":
    asyncio.run(main())
