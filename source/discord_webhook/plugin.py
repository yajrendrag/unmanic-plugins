#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               Brenden "Baconing" Freier <iam@baconi.ng>
    Date:                     14 Jan 2025

    Copyright:
        Copyright (C) 2025 Brenden "Baconing" Freier

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import logging
from discord_webhook import DiscordEmbed, DiscordWebhook
from unmanic.libs.unplugins.settings import PluginSettings

logger = logging.getLogger("Unmanic.Plugin.discord_webhook")

class Settings(PluginSettings):
    settings = {
        "Webhook URL": "",
        "Webhook Username": "",
        "Webhook Avatar URL": "",
        "Display Absolute Paths?": False,
        "Ping Everyone?": False
    }

def on_worker_process(data):
    logger.info("Sending notification to webhook for a started task.")
    settings = Settings(library_id=data['library_id'])

    webhookUrl = settings.get_setting("Webhook URL")
    absolutePaths = settings.get_setting("Display Absolute Paths?")
    pingEveryone = settings.get_setting("Ping Everyone?")
    username = settings.get_setting("Webhook Username")
    avatarUrl = settings.get_setting("Webhook Avatar URL")

    file = data["file_in"] if absolutePaths else data["file_in"].split("/")[-1]

    msg = DiscordWebhook(webhookUrl)
    msg.content = "@everyone" if pingEveryone else None
    msg.username = username if len(username) > 0 else None
    msg.avatar_url = avatarUrl if len(avatarUrl) > 0 else None
    
    embed = DiscordEmbed("Task Started", "A file processing task has begun.")
    embed.set_color(0xFFFF00)
    embed.add_embed_field("File", "```{}```".format(file), False)

    msg.add_embed(embed)

    resp = msg.execute()
    if not resp.ok:
        logger.error("Got failed status code %d from Discord: %s", resp.status_code, resp.json())
        resp.raise_for_status()


    return data

def on_postprocessor_task_results(data):
    settings = Settings(library_id=data['library_id'])

    webhookUrl = settings.get_setting("Webhook URL")
    absolutePaths = settings.get_setting("Display Absolute Paths?")
    pingEveryone = settings.get_setting("Ping Everyone?")
    username = settings.get_setting("Webhook Username")
    avatarUrl = settings.get_setting("Webhook Avatar URL")

    destination_files = ''.join(file if absolutePaths else file.split("/")[-1] for file in data["destination_files"])
    source_file = data["source_data"]["abspath"] if absolutePaths else data["source_data"]["basename"]

    msg = DiscordWebhook(webhookUrl)
    msg.content = "@everyone" if pingEveryone else None
    msg.username = username if len(username) > 0 else None
    msg.avatar_url = avatarUrl if len(avatarUrl) > 0 else None
    
    if (data["task_processing_success"] and data["file_move_processes_success"]):
        embed = DiscordEmbed("Task Completed", "A file processing task successfully completed.")
        embed.set_color(0x00FF00)
    else:
        embed = DiscordEmbed("Task Failed", "A file processing task failed during {}.".format("processing" if data["task_processing_success"] else "file movement"))
        embed.set_color(0xFF0000)

    embed.add_embed_field("File(s) Created", "```{}```".format(destination_files if len(destination_files) > 0 else "None"), False)
    embed.add_embed_field("Original (Source) File", "```{}```".format(source_file), False)

    msg.add_embed(embed)

    resp = msg.execute()
    if not resp.ok:
        logger.error("Got failed status code %d from Discord: %s", resp.status_code, resp.json())
        resp.raise_for_status()

    return data