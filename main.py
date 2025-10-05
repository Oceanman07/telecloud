import os
import asyncio
import time

from telethon import TelegramClient
from colorama import Style, Fore

from src.parser import load_config
from src.aes import generate_key
from src.protector import encrypt_key_test, decrypt_key_test
from src.telecloud.push import push_data
from src.telecloud.pull import pull_data
from src.constants import SESSION_PATH
from src.cloudmapmanager import (
    setup_cloudmap,
    check_health_cloudmap,
    get_cloud_channel_id,
    clean_prepared_data,
)


async def delete_msgs(client: TelegramClient):
    channel = await client.get_entity(get_cloud_channel_id())
    async for msg in client.iter_messages(channel):
        await client.delete_messages(channel, msg.id)


async def main():
    config = load_config()

    symmetric_key = b""
    if os.path.exists(SESSION_PATH + ".session"):
        symmetric_key = generate_key(config.password, config.salt)

        key_test_result = await decrypt_key_test(symmetric_key)
        if not key_test_result["success"]:
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Invalid password{Style.RESET_ALL}"
            )
            return

        await encrypt_key_test(symmetric_key)

    async with TelegramClient(
        SESSION_PATH, api_id=config.api_id, api_hash=config.api_hash
    ) as client:
        # await delete_msgs(client)
        # return

        if not check_health_cloudmap():
            await setup_cloudmap(client, config.api_id, config.api_hash)
            return

        try:
            if config.action == "push":
                await push_data(client, symmetric_key, config)

            elif config.action == "pull":
                await pull_data(client, symmetric_key, config)

        except KeyboardInterrupt:
            loop = asyncio.get_running_loop()
            for coro in asyncio.all_tasks(loop):
                coro.cancel()

    clean_prepared_data()


if __name__ == "__main__":
    asyncio.run(main())
