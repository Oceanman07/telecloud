import io
import random
import base64

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputChatUploadedPhoto
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
    DeleteChannelRequest,
)

from . import aes
from .icon import ICON
from .utils import read_file
from .constants import STRING_SESSION_PATH


def load_string_session(symmetric_key):
    encrypted_session = read_file(STRING_SESSION_PATH)
    session = aes.decrypt(symmetric_key, encrypted_session)

    return StringSession(session.decode())


async def create_channel(client: TelegramClient, title="TeleCloud", about="Free cloud"):
    channel = await client(CreateChannelRequest(title, about, megagroup=False))
    channel_id = channel.chats[0].id
    return int("-100" + str(channel_id))  # PeerChannel → -100 + channel ID


async def send_delete_confirmation_code(client: TelegramClient, cloud_channel_name):
    confirmation_code = str(random.randint(1000, 9999))
    msg = (
        f"Confirmation code to **delete __{cloud_channel_name}__**: {confirmation_code}"
    )
    await client.send_message("me", msg)
    return confirmation_code


async def delete_channel(client: TelegramClient, cloud_channel_id):
    channel = await client.get_entity(cloud_channel_id)
    await client(DeleteChannelRequest(channel))


async def set_channel_photo(
    client: TelegramClient, cloud_channel_id, file_name="icon.jpg"
):
    file_bytes = io.BytesIO(base64.b64decode(ICON))
    file_bytes.name = file_name

    uploaded_file = await client.upload_file(file_bytes)
    chat_photo = InputChatUploadedPhoto(uploaded_file)
    channel = await client.get_entity(cloud_channel_id)

    await client(EditPhotoRequest(channel, chat_photo))
