#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     25 October 2024, (11:00 AM)

    Copyright:
        Copyright (C) 2024 Jay Gardner

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import logging
from unmanic.libs.unplugins.settings import PluginSettings
import requests
import re
import urllib.parse
from plexapi.server import PlexServer
from plexapi.exceptions import PlexApiException
import os
import PTN
from bs4 import BeautifulSoup

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.notify_plex_partial")


class Settings(PluginSettings):
    settings = {
        'Plex URL':                'http://localhost:32400',
        'Plex Token':              '',
        'Unmanic Library Mapping':	'',
        'Notify on Task Failure?': False,
        'Analyze Video':           False,
    }

def get_section(media_dir, plex_url, plex_token):
    libs_url = plex_url + '/library/sections/?X-Plex-Token=' + plex_token
    logger.debug(f"libs_url: {libs_url}")
    sections = requests.get(libs_url)
    if sections:
        section_parse = re.findall(r'Location id=\"(.*)\" path=\"(.*)\" ', sections.text)
        if len(section_parse):
            for s in section_parse:
               if s[1] in media_dir:
                    return s[0]
    else:
        logger.error("Library section not found - '{}' - aborting".format(media_dir))
        return ""

def update_plex(plex_url, plex_token, media_dir, section_id):
    # Call to Plex to trigger an update
    logger.debug(f"media_dir: {media_dir}, section_id: {section_id}")
    plex_url = plex_url + '/library/sections/' + str(section_id) + '/refresh/?path=' + urllib.parse.quote(media_dir, safe='') + '&X-Plex-Token=' + plex_token
    logger.debug(f"plex_url: {plex_url}")
    response = requests.get(plex_url)
    if response.status_code == 200:
        logger.info("Notifying Plex ({}) to update its library.".format(plex_url))
    else:
        logger.error(f"return code: {response.status_code}")
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.error(f"Error text: {soup.get_text()}")
        except:
            logger.error(f"Can't parse error text")
        logger.error("Error requesting Plex to update: '{}'".format(media_dir))

def analyze_video(media_dir, plex_url, plex_token):
    headers = {'Accept': 'application/json'}
    try:
        plex = PlexServer(plex_url, plex_token)
    except PlexApiException as e:
        clean_msg = soup=BeautifulSoup(str(e), "html.parser").get_text().strip()
        logger.error(f"Auth failed: {clean_msg}; no analyze step will be performed.")
        return

    basename = os.path.splitext(os.path.basename(media_dir))[0]
    # this doesn't appear to be necessary and in fact causes the title to be incorrect
    # if there are extras after (year) as the title becomes the title string followed by the xtras string without the year
    # so the plex search fails.  if an example is found where this is needed, add a corner case to handle it, but do not 
    # make it exclusive.
    # basename = re.sub(r' \(\d\d\d\d\)','', basename)
    parsed_info = PTN.parse(basename, standardise = False)
    try:
        video = parsed_info['episodeName']
    except KeyError:
        video = parsed_info['title']

    logger.debug(f"basename: {basename}, parsed_info: {parsed_info}, video: {video}")

    item = plex.library.search(title=video)
    logger.debug(f"item: {item}")
    if not item:
        logger.error(f"Title {video} not found in plex library - no analyze step will be performed.")

    for i in item:
        i.analyze()
        if i.type == 'episode':
            logger.info(f"analyzing {i.show().title} Season {i.season().seasonNumber}, episode {i.episodeNumber}, {i.title}")
        else:
            logger.info(f"analyzing video {i.title}")

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    if not data.get('task_processing_success') and not settings.get_setting('Notify on Task Failure?'):
        return data

    try:
       media_dir = data.get('destination_files')[0]
    except IndexError:
       logger.error("Non-existent destination file - plex cannot be notified.")
       return data

    analyze = settings.get_setting('Analyze Video')

    # Get host mapping of library folder
    logger.debug(f"media_dir: {media_dir}")
    lib_map = settings.get_setting('Unmanic Library Mapping')
    logger.debug(f"lib_map: {lib_map}")
    host_dir=re.search(r'.*:(.*$)', lib_map)
    if host_dir:
        host_dir = host_dir.group(1)
    else:
        logger.error("unable to find identify host dir from mapping: '{}'".format(lib_map))
        return data
    unmanic_dir=re.search(r'(.*):', lib_map)
    if unmanic_dir:
        unmanic_dir = host_dir.group(1)
    else:
        logger.error("unable to find identify unmanic dir from mapping: '{}'".format(lib_map))
        return data
    plex_url = settings.get_setting('Plex URL')
    plex_token = settings.get_setting('Plex Token')
    logger.debug(f"plex_url: {plex_url}")
    logger.debug(f"plex_token: {plex_token}")
    logger.debug(f"host_dir: {host_dir}")
    try:
        media_dir = media_dir.replace(unmanic_dir,host_dir)
    except:
        logger.error("cannot form host media directory path - unmanic_dir: '{}', host_dir: '{}', media_dir: '{}'".format(unmanic_dir, host_dir, media_dir))
        return data
    logger.debug(f"media_dir: {media_dir}")
    section_id = get_section(media_dir, plex_url, plex_token)
    logger.debug(f"section_id: {section_id}")
    if not section_id:
        return data
    update_plex(plex_url, plex_token, media_dir, section_id)

    # Analyze Video
    if analyze:
        analyze_video(media_dir, plex_url, plex_token)

    return data
