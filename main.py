import os
import asyncio
import time

from dotenv import load_dotenv
from colorama import Style, Fore
from telethon import TelegramClient

from src.parser import load_config
from src.aes import generate_key
from src.telecloud.push import push_data
from src.telecloud.pull import pull_data
from src.constants import SESSION_PATH
from src.cloudmapmanager import (
    setup_cloudmap,
    check_health_cloudmap,
    get_cloud_channel_id,
    get_salt_from_cloudmap,
    clean_prepared_data,
)

load_dotenv()
api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]


async def delete_msgs(client: TelegramClient):
    channel = await client.get_entity(get_cloud_channel_id())
    async for msg in client.iter_messages(channel):
        await client.delete_messages(channel, msg.id)


async def main():
    config = load_config()

    async with TelegramClient(SESSION_PATH, api_id=api_id, api_hash=api_hash) as client:
        # await delete_msgs(client)
        # return

        try:
            if not check_health_cloudmap():
                await setup_cloudmap(client)

            salt = get_salt_from_cloudmap()
            symmetric_key = generate_key(config.password, salt)

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
