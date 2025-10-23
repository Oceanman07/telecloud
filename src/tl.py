import io
import base64

from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest
from telethon.tl.types import InputChatUploadedPhoto

from .icon import ICON


async def create_channel(client: TelegramClient, title="TeleCloud", about="Free cloud"):
    channel = await client(CreateChannelRequest(title, about, megagroup=False))
    channel_id = channel.chats[0].id
    return int("-100" + str(channel_id))  # PeerChannel → -100 + channel ID


async def set_channel_photo(
    client: TelegramClient, cloud_channel_id, file_name="icon.jpg"
):
    file_bytes = io.BytesIO(base64.b64decode(ICON))
    file_bytes.name = file_name

    uploaded_file = await client.upload_file(file_bytes)
    chat_photo = InputChatUploadedPhoto(uploaded_file)
    channel = await client.get_entity(cloud_channel_id)

    await client(EditPhotoRequest(channel, chat_photo))
