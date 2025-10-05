import os
import asyncio
import time

from colorama import Style, Fore
from telethon import TelegramClient
from telethon.sessions import StringSession

from src.parser import load_config
from src.aes import generate_key
from src.protector import encrypt_string_session, decrypt_string_session
from src.telecloud.push import push_data
from src.telecloud.pull import pull_data
from src.utils import write_file
from src.constants import STRING_SESSION_PATH
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

    loop = asyncio.get_running_loop()

    session = StringSession()
    symmetric_key = generate_key(config.password, config.salt)

    if os.path.exists(STRING_SESSION_PATH):
        result = await decrypt_string_session(symmetric_key)
        if not result["success"]:
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - {result['error']}{Style.RESET_ALL}"
            )
            return

        session = StringSession(result["string_session"])

        await loop.run_in_executor(
            None, write_file, STRING_SESSION_PATH, result["string_session"], "w"
        )
        await encrypt_string_session(symmetric_key)

    async with TelegramClient(
        session, api_id=config.api_id, api_hash=config.api_hash
    ) as client:
        # await delete_msgs(client)
        # return

        if not check_health_cloudmap():
            string_session = session.save()
            await setup_cloudmap(client, string_session, config.api_id, config.api_hash)
            return

        try:
            if config.action == "push":
                await push_data(client, symmetric_key, config)

            elif config.action == "pull":
                await pull_data(client, symmetric_key, config)

        except KeyboardInterrupt:
            for coro in asyncio.all_tasks(loop):
                coro.cancel()

    clean_prepared_data()


if __name__ == "__main__":
    asyncio.run(main())
