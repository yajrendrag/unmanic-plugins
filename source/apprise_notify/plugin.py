#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     29 September 2023, (11:00 PM)

    Copyright:
        Copyright (C) 2023 Jay Gardner

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

        This program uses the Apprise Project (<https://github.com/caronc/apprise/>) which is governed by it's own
        license terms using BSD 3-Clause "New" or "Revised" License.  The text of this license has accompanied this
        program.  If for some reason you do not have it, please refer to <https://github.com/caronc/apprise/blob/master/LICENSE/>.

"""
import logging
import apprise

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.apprise_notify")


class Settings(PluginSettings):
    settings = {
        'apprise_config_path':    '/config/apprise_config.txt'
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)


def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        library_id                      - The library that the current task is associated with.
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

    status = data.get('task_processing_success')
    if status:
        task_status = "successfully processed"
    else:
        task_status = "failed to process"
    apprise_config_path = str(settings.get_setting('apprise_config_path'))
    source = data.get('source_data')["basename"]
    notify = apprise.Apprise()
    config = apprise.AppriseConfig()
    result = config.add(apprise_config_path)
    if not result:
        logger.error("Error adding apprise configuration")
        return data
    result = notify.add(config)
    if not result:
        logger.error("Error adding configuration data to apprise notification object")
        return data
    result = notify.notify(body='Unmanic ' + str(task_status) + str('\n') + str(source), title = 'Unmanic Task Status')
    if not result:
        logger.error("Error sending apprise notification")
    return data
