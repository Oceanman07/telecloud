from ..config_manager.config import Config
from ..config_manager.functions import (
    add_password_to_config,
    remove_password_from_config,
    change_password,
    change_new_default_pulled_directory,
    show_all_config_setting,
    create_new_cloud_channel,
    switch_cloud_channel,
    delete_cloud_channel,
    show_all_cloud_channels,
)


def set_general_config(config: Config):
    if config.is_auto_fill_password == "true":
        add_password_to_config(config.password)

    elif config.is_auto_fill_password == "false":
        remove_password_from_config()

    elif config.new_password:
        change_password(config.password, config.new_password)

    elif config.new_default_pulled_dir:
        change_new_default_pulled_directory(config.new_default_pulled_dir)

    else:
        show_all_config_setting()


async def set_cloud_channel_config(config: Config, client=None):
    if config.new_cloudchannel:
        await create_new_cloud_channel(client)

    elif config.switched_cloudchannel:
        switch_cloud_channel(config.switched_cloudchannel)

    elif config.deleted_cloudchannel:
        await delete_cloud_channel(client, config.deleted_cloudchannel)

    else:
        show_all_cloud_channels()
