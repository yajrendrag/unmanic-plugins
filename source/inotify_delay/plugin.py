#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     17 November 2024, (08:30 AM)

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
import os
import subprocess
import time

from unmanic.libs.unplugins.settings import PluginSettings

v_sfx = ['m4v', '3gp', 'axv', 'dl', 'dif', 'dv', 'fli', 'gl', 'mpeg', 'mpg', 'mpe', 'ts', 'mp4', 'qt', 'mov', 'ogv', 'webm', 'mxu', 'flv', 'lsf', 'lsx', 'mng', 'asf', 'asx', 'wm', 'wmv', 'wmx', 'wvx', 'avi', 'movie', 'mpv', 'mkv']

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.inotify_delay")


class Settings(PluginSettings):
    settings = {
        "notify_window":    "15",
        "size_window":      "30"
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "notify_window": {
                "label": "Enter the value for the window of time (whole seconds) inotify should monitor the file for events.  The window is checked until no events are detected",
            },
            "size_window": {
                "label": "Enter the value for the amount (whole seconds) of time in between size checks on the file.  Size checks are repeated at this frequency until no changes in size are detected",
            }
        }

def test_notify_events(f, notify_window):
    result=subprocess.run(["/usr/bin/inotifywait", "-t", notify_window, "-e", "close", f], capture_output=True, text=True)
    logger.debug("result.stdout: '{}'".format(result.stdout))
    if result.stdout == '':
        return True
    else:
        return False

def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        exec_command            - A command that Unmanic should execute. Can be empty.
        command_progress_parser - A function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - The source file to be processed by the command.
        file_out                - The destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - The absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:

    """

    # Get the path to the file
    abspath = data.get('original_file_path')
    outpath = data.get('file_out')

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    notify_window = settings.get_setting('notify_window')
    size_window = int(settings.get_setting('size_window'))

    # Test if file is generating inotify events
    while True:
        notify = test_notify_events(abspath, notify_window)
        if notify:
            break

    # Test if file size is remaining constant
    stats = os.stat(abspath)
    size = stats.st_size
    while True:
        time.sleep(size_window)
        stats = os.stat(abspath)
        size_new = stats.st_size
        if size_new - size == 0:
            break
        size = size_new

    # reaching this point implicity suggests the file is completely moved into place and can be processed
    # Since the plugin is first in the worker process, then plugin should automatically copy the source

    logger.debug("file_in: '{}'; file_out: '{}'".format(data['file_in'], data['file_out']))

    # Default to no command
    data['exec_command'] = []

    # if file had a temporary suffix try and remove it from data['file_in'], data['file_out']
    file_ext = os.path.splitext(abspath)[1]
    if file_ext == '.part':
        b=os.path.split(abspath)[1]
        nfn = ''
        for p in re.findall(r'(.*?)\.', b):
            if p in v_sfx:
                lastp = p
        for p in re.findall(r'(.*?)\.', b):
            if p != lastp:
                if nfn == '':
                    nfn = p
                else:
                    nfn += '.' + p
            else:
                    nfn += '.' + p
                    break
        new_file_name = os.path.split(abspath)[0] + '/' + nfn
        data['file_in'] = new_file_name
        s1 = abspath.split('.')
        s2 = nfn.split('.')
        s1s = set(s1)
        s2s = set(s2)
        sd = s1s.symmetric_difference(s2s)
        new_output_file = outpath
        for i in sd:
            new_output_file = new_output_file.replace('.'+i, '')
        data['file_out'] = new_output_file

    return data
