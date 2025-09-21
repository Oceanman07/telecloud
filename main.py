import os
import asyncio

from dotenv import load_dotenv
from telethon import TelegramClient

from src.parser import parse_args
from src.telecloud import push_data, pull_data
from src.elements import SESSION_PATH
from src.cloudmapmanager import check_health_cloudmap, setup_cloudmap

load_dotenv()
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']


async def delete_msgs(client: TelegramClient):
    async for msg in client.iter_messages('me'):
        await client.delete_messages('me', msg.id)

async def main():
    args = parse_args()

    async with TelegramClient(SESSION_PATH, api_id=api_id, api_hash=api_hash) as client:
        # await delete_msgs(client)
        # return

        if not check_health_cloudmap():
            setup_cloudmap()

        if args.push:
            await push_data(client, args.directory, args.password)

        elif args.pull:
            await pull_data(client, args.directory, args.password)

if __name__ == '__main__':
    asyncio.run(main())

