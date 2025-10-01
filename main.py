import os
import asyncio

from dotenv import load_dotenv
from telethon import TelegramClient

from src.parser import parse_args
from src import aes
from src.telecloud import push_data, pull_data
from src.elements import SESSION_PATH
from src.cloudmapmanager import (
    check_health_cloudmap,
    get_cloud_channel_id,
    setup_cloudmap,
    get_salt_from_cloudmap,
)

load_dotenv()
api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]


async def delete_msgs(client: TelegramClient):
    channel = await client.get_entity(get_cloud_channel_id())
    async for msg in client.iter_messages(channel):
        await client.delete_messages(channel, msg.id)


async def main():
    args = parse_args()

    async with TelegramClient(SESSION_PATH, api_id=api_id, api_hash=api_hash) as client:
        # await delete_msgs(client)
        # os.remove("/Users/supertempclient/.telecloud/cloudmap.json")
        # return

        if not check_health_cloudmap():
            await setup_cloudmap(client)

        salt = get_salt_from_cloudmap()
        symmetric_key = aes.generate_key(args.password, salt)

        try:
            if args.push:
                await push_data(client, symmetric_key, args.directory)

            elif args.pull:
                await pull_data(client, symmetric_key, args.directory)

        except KeyboardInterrupt:
            loop = asyncio.get_running_loop()
            for coro in asyncio.all_tasks(loop):
                coro.cancel()


if __name__ == "__main__":
    asyncio.run(main())
