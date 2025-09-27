#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     26 September 2025, (11:24 PM)

    Copyright:
        Copyright (C) 2025 Jay Gardner

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
import glob
import re
import shutil
import hashlib
import concurrent.futures
import requests
import json
from pathlib import Path

from unmanic.libs.unplugins.settings import PluginSettings

from unmanic import config

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.inotify_delay_st")


class Settings(PluginSettings):
    settings = {
        "notify_window":    "15",
        "unmanic_ip_port":  "192.168.1.100:8888",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "notify_window": {
                "label": "Notify Window Size",
                "description": "Enter the value for the window of time (whole seconds) inotify should monitor the file for events.  The window is checked until no events are detected",
                "input_type":     "slider",
                "slider_options": {
                    "min":    1,
                    "max":    30,
                    "step":   1,
                },
            },
            "unmanic_ip_port": {
                "label": "Enter unmanic host ip address and port",
                "input_type": "textarea",
            },
        }

def test_notify_events(f, notify_window):
    result=subprocess.run(["/usr/bin/inotifywait", "-t", notify_window, "-e", "close", f], capture_output=True, text=True)
    logger.debug("result.stdout: '{}'".format(result.stdout))
    if result.stdout == '':
        return True
    else:
        return False

def inotify_loop(abspath, notify_window):
    # Test if file is generating inotify events
    start = time.time()
    while True:
        notify = test_notify_events(abspath, notify_window)
        if notify:
            return "abspath is complete"
        if time.time() - start > 600:
            return "abspath download exceeding 10 minutes"

def st_tmp_file_loop(file_base):
    start = time.time()
    st_tmp_file_found = False
    while True:
        st_tmp_file = glob.glob(file_base + '.tmp.*')
        if not st_tmp_file and st_tmp_file_found:
            return "st_tmp_file created and deleted"
        else:
            st_tmp_file_found = True
        if time.time() - start > 30:
            return "st_tmp_file discovery timed out"

def renamed_file_loop(abspath):
    abspath_dir = os.path.dirname(abspath)
    abspath_base = os.path.basename(abspath)
    pattern = r'^.* - S[0-9]+E[0-9]+ - .* - \[.*$'
    pattern2 = '^.*S[0-9]+E[0-9]+ -.*- '
    start = time.time()
    while True:
        renamed_file = [f for f in glob.glob(abspath_dir + '/*.mkv') if re.match(pattern2, abspath_base) and re.match(pattern, f)]
        if len(renamed_file) == 1:
            return renamed_file
        if time.time() - start > 30:
            if len(renamed_file) > 0:
                return renamed_file
            elif len(renamed_file) == 0:
                return "error - unable to discover renamed file"

def renamed_file_task_loop(abspath):
    abspath_dir = os.path.dirname(abspath)
    abspath_base = os.path.basename(abspath)
    pattern = r'^.* - S[0-9]+E[0-9]+ - .* - \[.*$'
    pattern2 = '^.*S[0-9]+E[0-9]+ -.*- '
    start = time.time()
    while True:
        renamed_file = [f for f in glob.glob(abspath_dir + '/*.mkv') if re.match(pattern2, abspath_base) and re.match(pattern, f)]
        if len(renamed_file) == 1:
            delete_pending_running_tasks(renamed_file[0])
            return "renamed file tasks deleted"
        elif time.time() - start > 300:
            return "no renamed file tasks created in 5 minutes"


def delete_pending_running_tasks(rfile, settings):
    unmanic_addr = settings.get_setting("unmanic_ip_port")
    headers = {'Content-Type': 'application/json'}
    base_file = os.path.basename(rfile)
    task_deleted = False

    # check pending tasks (pt)
    pt_payload = json.dumps({"start": 0, "status": "all", "search_value": rfile})
    pt_url = "http://" + unmanic_addr + "/unmanic/api/v2/pending/tasks"
    pt_response = requests.request("POST", pt_url, headers=headers, data=pt_payload)
    pending_tasks = pt_response.json()
    if pending_tasks:
        task_to_delete = pending_tasks['results'][0]['id'] if pending_tasks['results'][0]['abspath'] == rfile else ""
        if task_to_delete:
            del_url = "http://" + unmanic_addr + "/unmanic/api/v2/history/tasks"
            del_payload = json.dumps({"id_list": [int(task_to_delete)]})
            del_payload_response = requests.request("DELETE", del_url, headers=headers, data=del_payload)
            logger.debug(f"del_payload_response to deleting task {task_to_delete} for renamed file: {rfile}: {del_payload_response.text}")
            task_deleted = True
        else:
            logger.debug(f"no pending task for file: {rfile}")
    else:
        logger.debug(f"no pending task for file: {rfile}")

    # check running tasks (rt)
    rt_payload = ""
    rt_url = "http://" + unmanic_addr + "/unmanic/api/v2/workers/status"
    rt_response = requests.request("GET", rt_url, headers=headers, data=rt_payload)
    running_tasks = rt_response.json()['workers_status']
    worker_to_stop = [running_tasks[i]['id'] for i in range(len(running_tasks)) if running_tasks[i]['current_file'] == base_file]
    if worker_to_stop:
        worker_payload =  json.dumps({"worker_id": worker_to_stop[0]})
        worker_url = "http://" + unmanic_addr + "/unmanic/api/v2/workers/worker/terminate"
        worker_term_response = requests.request("DELETE", worker_url, headers=headers, data=worker_payload)
        logger.debug(f"worker_term_response to terminating worker id {worker_to_stop[0]}: {worker_term_response.text}")
        task_deleted = True
    else:
        logger.debug(f"no worker currently running task for file: {rfile}")

    return task_deleted

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

    file_base = os.path.splitext(abspath)[0]

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    notify_window = settings.get_setting('notify_window')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(inotify_loop, abspath, notify_window), executor.submit(st_tmp_file_loop, file_base), executor.submit(renamed_file_loop, abspath), executor.submit(renamed_file_task_loop, abspath)]
        results = [future.result() for future in futures]

    if results[0] == "abspath is complete" and results[1] == "st_tmp_file created and deleted" and (type(results[2]) is list and len(results[2]) == 1):
        renamed_file = renamed_file[0]
        if renamed_file != abspath:
            task_deleted = delete_pending_running_tasks(renamed_file, settings)
            if task_deleted:
                shutil.move(renamed_file, abspath)
            else:
                logger.error(f"Something went wrong - the striptracks renamed file was found, but no pending or running tasks could be identified.  aborting.")
                return
    else:
        logger.error(f"Something went wrong and the striptracks renamed file could not be identified.  aborting.")
        logger.error(f"results[0]: {results[0]}")
        logger.error(f"results[1]: {results[1]}")
        logger.error(f"results[2]: {results[2]}")
        logger.error(f"results[3]: {results[3]}")
        return

    # save renamed_file name to restore in postprocessor
    src_file_hash = hashlib.md5(os.path.basename(abspath).encode('utf8')).hexdigest()
    settings2 = config.Config()
    cache_path = settings2.get_cache_path()
    tmp_dir = os.path.join(cache_path, '{}'.format(src_file_hash))
    dir=Path(tmp_dir)
    dir.mkdir(parents=True, exist_ok=True)
    command = ['touch', tmp_dir + '/' + renamed_file]
    result = subprocess.run(command, shell=False, check=True, capture_output=True)

    logger.debug(f"striptracks file name: {renamed_file}, original source file name: {abspath}")

    # reaching this point implicity suggests the file was picked up by file monitor and striptracks
    # renamed the file. unmanic renamed the file back to the original source file name and saved
    # the renamed file name for later use.  the plugin concludes by copying the file to the cache.

    logger.debug("file_in: '{}'; file_out: '{}'".format(data['file_in'], data['file_out']))

    # Default to no command
    data['exec_command'] = ['cp', '-a', abspath, outpath]

    return data

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

    if data.get('task_processing_success'):
        # copy source file to saved name from striptracks rename
        srcpath = data.get('source_data')['abspath']
        src_file_hash = hashlib.md5(os.path.basename(srcpath).encode('utf8')).hexdigest()
        settings2 = config.Config()
        cache_path = settings2.get_cache_path()
        tmp_dir = os.path.join(cache_path, '{}'.format(src_file_hash))
        dir=Path(tmp_dir)
        command = ['ls', '-1', tmp_dir + '/' + renamed_file]
        try:
            result = subprocess.run(command, shell=False, check=True, capture_output=True, text=True)
        except:
            logger.error(f"striptracks file name not found, original filename left intact")
        else:
            renamed_file = result.stdout.replace('\n','')
            shutil.move(srcpath, renamed_file)
            logger.info(f"File {srcpath} moved to striptracks filename {renamed_file}")

    # remove temp files and directory
    for f in glob.glob("*.*", root_dir=tmp_dir):
        os.remove(tmp_dir + f)
    shutil.rmtree(tmp_dir)

    return
