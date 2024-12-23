#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     3 Dec 2024, (17:45 PM)

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
import ffmpeg
import hashlib
import shutil
import glob
import re
import shlex
import PTN
import requests
import subprocess

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.split_mkv")

class Settings(PluginSettings):
    settings = {
        "split_method":          "",
        "season_dir":            True,
        "keep_original":         False,
        "min_silence":           "",
        "min_black":             "",
        "tmdb_api_key":              "",
        "tmdb_api_read_access_token":    "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "split_method":        self.__set_split_method_form_settings(),
            "season_dir":    {
                 "label":    "check this to create a new Season subdirectory in the folder containing the multi episode file is",
            },
            "keep_original": {
                 "label":    "check this to keep the original multiepisode file, otherwise it is deleted",
            },
            "min_silence":         self.__set_min_silence_form_settings(),
            "min_black":           self.__set_min_black_form_settings(),
            "tmdb_api_key": self.__set_tmdb_api_key_form_settings(),
            "tmdb_api_read_access_token": self.__set_tmdb_api_read_access_token_form_settings(),
        }

    def __set_split_method_form_settings(self):
        values = {
            "label":        "Enter Choice",
            "description":  "Select method of splitting file - chapter marks or time value",
            "input_type": "select",
            "select_options": [
                {
                    "value": "chapters",
                    "label": "Chapter Marks",
                },
                {
                    "value": "time",
                    "label": "Time Interval",
                },
                {
                    "value": "combo",
                    "label": "Chapter Marks with fallback of Time Interval",
                },
                {
                    "value": "sbi",
                    "label": "Identify chapters based on Silence/Black intervals",
                },
                {
                    "value": 'tmdb',
                    "label": 'Create chapter marks based on looking up episode duration on tmdb',
                },
            ],
        }
        return values

    def __set_min_silence_form_settings(self):
        values = {
            "label":          "Time",
            "description":    "Minimum time for a silence interval to identify an episode change",
            "input_type":     "slider",
            "slider_options": {
                "min": 1,
                "max": 10,
                "step": 0.1
            }
        }
        if self.get_setting('split_method') != 'sbi':
            values["display"] = 'hidden'
        return values

    def __set_min_black_form_settings(self):
        values = {
            "label":          "Time",
            "description":    "Minimum time for a black interval to identify an episode change",
            "input_type":     "slider",
            "slider_options": {
                "min": 1,
                "max": 10,
                "step": 0.1
            }
        }
        if self.get_setting('split_method') != 'sbi' and self.get_setting('split_method') != 'tmdb':
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_key_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api key",
            "input_type": "textarea",
        }
        if self.get_setting('split_method') != 'tmdb':
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_read_access_token_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api api read access token",
            "input_type": "textarea",
        }
        if self.get_setting('split_method') != 'tmdb':
            values["display"] = 'hidden'
        return values

def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.

    :param data:
    :return:

    """
    # Get the path to the file
    abspath = data.get('path')

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    basename = os.path.split(abspath)[1]
    base_noext = os.path.splitext(basename)[0]
    duration = float(ffmpeg.probe(abspath)["format"]["duration"])
    n_episodes = get_last_episode(base_noext) - get_first_episode(base_no_ext) + 1

    match = re.search(r'.*(S\d+[ -]*E\d+ *- *E*\d+).*$', base_noext)
    if not match:
        logger.info("File name does not indicate presence of multiple episodes. Aborting")
        return data

    split_method = settings.get_setting('split_method')
    if split_method != 'chapters':
        chapter_time = duration / n_episodes

    if split_method == 'chapters' or split_method == 'combo':
        chapters = ffmpeg.probe(abspath, show_chapters=None)['chapters']
        if chapters:
            logger.info("Splitting file '{}' based on presence of '{}' chapters".format(abspath, len(chapters)))
            data['add_file_to_pending_tasks'] = True
            return data
        else:
            if split_method != 'combo':
                logger.info("No chapters found and split_method = chapters. Aborting")
                return data
    if split_method == 'combo' or split_method == 'time':
        logger.info("Splitting file '{}' based on chapter times of '{}' minutes".format(abspath, chapter_time))
        data['add_file_to_pending_tasks'] = True
        return data

    if split_method == 'sbi' or split_method == 'tmdb':
        if split_method == 'sbi':
            method = 'scene detection'
        else:
            method = 'tmdb lookup'
        logger.info("Splitting file '{}' by creating chapters based on '{}'".format(abspath, method))
        data['add_file_to_pending_tasks'] = True
        return data

def get_split_details(srcpath):
    split_base = os.path.split(srcpath)[1]
    split_base_noext = os.path.splitext(split_base)[0]
    sfx = os.path.splitext(split_base)[1]
    return split_base, split_base_noext, sfx

def get_overlap(interval1, interval2):
     start = max(interval1[0], interval2[0])
     end = min(interval1[1], interval2[1])
     overlap = max(0, (end - start))
     return overlap

def get_first_episode(f):
    match = re.search(r'.*S\d+[ -]*E(\d+).*$', f)
    if match:
        try:
            first_episode = int(match.group(1))
        except ValueError:
            raise ValueError('match didnt produce a valid starting episode number')
            return -1
    return first_episode

def get_last_episode(f):
    match = re.search(r'.*S\d+[ -]*E\d+[ -]+E*(\d+).*$', f)
    if match:
        try:
            last_episode = int(match.group(1))
        except ValueError:
            raise ValueError('match didnt produce a valid ending episode number')
            return -1
    return last_episode

def dur2hms(dur):
     h = int(dur/3600)
     rdurm = dur - h*3600
     m = int(rdurm/60)
     s = rdurm - m*60
     return f"{h:02d}:{m:02d}:{s:06.3f}"

def prep_sb_file(srcpath, split_base, split_base_noext, cache_file):
    # analyze file and find silence and black screen intervals
    b_detect_int = settings.get_setting('min_black')
    s_detect_int = settings.get_setting('min_silence')
    dlog=open(tmp_dir + 'detection.log', 'w', encoding='utf-8')
    r=subprocess.run(['ffmpeg', '-progress', 'pipe:1', '-v', 'quiet', '-loglevel', 'info', '-i', srcpath, '-vf', 'blackdetect=d=' + b_detect_int + ':pix_th=0.1', '-af', 'silencedetect=n=-50dB:d=' + s_detect_int, '-f', 'null', '-'], stderr=dlog, stdout=dlog)
    if r.returncode > 0:
        logger.error("Unable to capture silence or black scenes in '{}' - aborting".format(srcpath))
        raise Exception("Scene detection Error")
        return
    dlog.close()
    duration = float(ffmpeg.probe(srcpath)["format"]["duration"])

    # process resulting detection log and parse to relevant lines to form mkv chapters
    fout=open(tmp_dir + 'det.log', 'w', encoding='utf-8')
    with open(tmp_dir + 'detection.log') as input:
        out = subprocess.run(['grep', '-e', 'silence_', '-e', 'black_'], stdin=input, stdout=fout)
    r=subprocess.run(['sed', '-i', 's/\\[[black|silence].*\\] //g', tmp_dir + 'det.log'])
    if r.returncode > 0:
        logger.error("Unable to process scene detection capture - '{}' - aborting".format(srcpath))
        raise Exception("Scene detection processing Error")
        return
    sed_script=r"':a' -e '$!N;s/\(.*\)\n\(.*silence_end.*\)/\1 \2/;ta' -e 'P;D'"
    command = f"sed -i -e {sed_script}"
    args = shlex.split(command)
    fdetlog = tmp_dir + 'det.log'
    args.append(fdetlog)
    r= subprocess.run(args, capture_output=True, text=True)
    if r.returncode > 0:
        logger.error("Unable to process scene detection capture - '{}' - aborting".format(srcpath))
        raise Exception("Scene detection processing Error")
        return
    fout.close()
    return

def print_chap_file(tmp_dir, chapters, first_episode, chap_ep):
    with open(tmp_dir + 'chapters.xml', 'a') as chap_file:
        print('<?xml version="1.0" encoding="ISO-8859-1"?>', file=chap_file)
        print('<!DOCTYPE Chapters SYSTEM "matroskachapters.dtd">', file=chap_file)
        print('<Chapters>', file=chap_file)
        print('  <EditionEntry>', file=chap_file)
        for i in range(1, chap_ep + 1):
            print('    <ChapterAtom>', file=chap_file)
            hms=dur2hms(chapters[i-1]["start"])
            print(f'      <ChapterTimeStart>{hms}</ChapterTimeStart>', file=chap_file)
            hms=dur2hms(chapters[i-1]["end"])
            print(f'      <ChapterTimeEnd>{hms}</ChapterTimeEnd>', file=chap_file)
            print('      <ChapterDisplay>', file=chap_file)
            print(f'        <ChapterString>Episode {first_episode + i -1}</ChapterString>', file=chap_file)
            print('      </ChapterDisplay>', file=chap_file)
            print('    </ChapterAtom>', file=chap_file)
        print('  </EditionEntry>', file=chap_file)
        print('</Chapters>', file=chap_file)
    return

def get_chapters_from_sb_intervals(srcpath, tmp_dir, settings):
    """
    Use ffmpeg silencedetect / blackdetect filters to identify the end of prior and start of next episode
    """

    # remove any existing chapter marks and write to cache
    split_base, split_base_noext, sfx = get_split_details(srcpath)
    cache_file = tmp_dir + split_base
    r = subprocess.run(['cp', '-a', srcpath, cache_file], capture_output=True)
    if r.returncode > 0:
        logger.error("Unable to copy source to cache - '{}' - aborting".format(srcpath))
        raise Exception("Cache copy issue")
        return
    r = subprocess.run(['mkvpropedit', cache_file, '--chapters', ''], capture_output=True)
    if r.returncode > 0:
        logger.error("Unable to remove existing chapter marks - '{}' - aborting".format(srcpath))
        raise Exception("Chapter marks removal issue")
        return
    prep_sb_file(srcpath, split_base, split_base_noext, cache_file)

    # analyze parsed detection log into chapter start/end times on which chapters will be formed
    intervals=open(tmp_dir + 'det.log', 'rt', encoding='utf-8')
    lines=intervals.readlines()
    intervals.close()

    # get starting episode number
    first_episode = get_first_episode(split_base_noext)
    last_episode = get_last_episode(split_base_noext)
    chapters = []
    chap_ep = 1
    chapters.append({"start": 0.0})
    logger.debug("first_episode: '{}', last_episode: '{}'".format(first_episode, last_episode))

    # find chapter start / end times based on silence and black detected intervals
    for i in range((len(lines) - 1)):
        if ("silence" in lines[i] and "silence" in lines[i+1]) or ("black" in lines[i] and "black" in lines[i+1]):
            continue
        if "silence" in lines[i] and "black" in lines[i+1]:
            ss=re.search(r'silence_start: (\d+\.\d+).*$', lines[i])
            se=re.search(r'.*silence_end: (\d+\.\d+).*$', lines[i])
            silence=(float(ss.group(1)), float(se.group(1)))
            bs=re.search(r'black_start: *(\d+\.\d+).*$', lines[i+1])
            be=re.search(r'.*black_end: *(\d+\.\d+).*$', lines[i+1])
            black=(float(bs.group(1)), float(be.group(1)))
        elif "black" in lines[i] and "silence" in lines[i+1]:
            bs=re.search(r'black_start: *(\d+\.\d+).*$', lines[i])
            be=re.search(r'.*black_end: *(\d+\.\d+).*$', lines[i])
            black=(float(bs.group(1)), float(be.group(1)))
            ss=re.search(r'silence_start: (\d+\.\d+).*$', lines[i+1])
            se=re.search(r'.*silence_end: (\d+\.\d+).*$', lines[i+1])
            silence=(float(ss.group(1)), float(se.group(1)))
        logger.debug("chap_ep: '{}'".format(chap_ep))
        overlap = get_overlap(silence, black)
        logger.debug("overlap: '{}'".format(overlap))
        if overlap and i < len(lines) - 1:
            logger.debug("Overlap of '{}' seconds on interval '{}' betweeen silence and black intervals, high confidence interval represents a new episode.  Video: '{}'".format(overlap, i/2+1, split_base_noext))
            chap_start = float(max(se.group(1), be.group(1)))
            chap_end = float(min(ss.group(1), bs.group(1)))
            chapters[chap_ep-1].update({"end": chap_end})
            chap_ep += 1
            chapters.append({"start": chap_start})
        logger.debug("chapters: '{}'".format(chapters))
    if "end" not in chapters[chap_ep-1]:
        chapters[chap_ep-1].update({"end": duration})
    if chap_ep == 1:
        logger.info("no chapters found based on silence/black scene detection mode, '{}'".format(srcpath))
    else:
        logger.info("Chapters derived from silence/black scene changes, '{}' chapters, '{}' episodes in file '{}'".format(chap_ep, last_episode - first_episode + 1))

    if chap_ep > 1:
        print_chap_file(tmp_dir, chapters, first_episode, chap_ep)
        r = subprocess.run(['mkvpropedit', cache_file, '--chapters', tmp_dir + 'chapters.xml'], capture_output=True)
        return [True]

def get_chapters_based_on_tmdb(srcpath, tmp_dir, settings):
    """
    lookup episode duration on tmdb.  couple this with black scene detection to identify chapter end.
    """
    # remove any existing chapter marks and write to cache
    split_base, split_base_noext, sfx = get_split_details(srcpath)
    cache_file = tmp_dir + split_base
    r = subprocess.run(['cp', '-a', srcpath, cache_file], capture_output=True)
    if r.returncode > 0:
        logger.error("Unable to copy source to cache - '{}' - aborting".format(srcpath))
        raise Exception("Cache copy issue")
        return
    r = subprocess.run(['mkvpropedit', cache_file, '--chapters', ''], capture_output=True)
    if r.returncode > 0:
        logger.error("Unable to remove existing chapter marks - '{}' - aborting".format(srcpath))
        raise Exception("Chapter marks removal issue")
        return

    prep_sb_file(srcpath, split_base, split_base_noext, cache_file)

    tmdb_api_key = settings.get_setting("tmdb_api_key")
    tmdb_api_read_access_token = settings.get_setting("tmdb_api_read_access_token")
    tmdburl = 'https://api.themoviedb.org/3/search/tv?query='
    tmdb_season_url = 'https://api.themoviedb.org/3/tv/'
    headers = {'accept': 'application/json', 'Authorization': 'Bearer ' + tmdb_api_read_access_token}

    parsed_info = PTN.parse(split_base, standardise=False)

    try:
        title = parsed_info["title"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(srcpath))

    try:
        episodes = parsed_info['episode']
    except KeyError:
        episode = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))

    try:
        season = parsed_info["season"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(srcpath))

    vurl = tmdburl + title + '&api_key=' + tmdb_api_key
    try:
        video = requests.request("GET", vurl, headers=headers)
        id = video.json()["results"][0]['id']
    except:
        logger.error("Error requesting video info from tmdb. Aborting")
        return False

    if type(episodes) == list:
        first_episode = episodes[0]
        last_episode = episodes[len(episodes) -1]
    elif type(episodes) == int:
        first_episode = episodes
        last_episode = episodes
    else:
        logger.error("Episodes not successfully parsed from video file: '{}'".format(srcpath))
        raise Exception("Episodes not successfully parsed")
        return False

    # use black scene detection near tmdb episode duration to corroborate episode end & mark episode +1 start
    intervals=open(tmp_dir + 'det.log', 'rt', encoding='utf-8')
    lines=intervals.readlines()
    intervals.close()

    chapters = []
    chap_ep = 1
    chapters.append({"start": 0.0})
    episode_runtimes = []
    for episode in range(first_episode, last_episode):
        show_url = tmdb_season_url + str(id) + '/season/' + str(season) + '/episode/' + str(episode)
        episode_result = requests.request("GET", show_url, headers=headers)
        episode_duration = float(episode_result.json()['runtime'])
        episode_runtimes.append(episode_duration * 60.0)
        cumulative_runtime = sum(float(i) for i in episode_runtimes)
        chapters[chap_ep-1].update({"end": cumulative_runtime})
        chap_start = cumulative_runtime + 2
        for i in range((len(lines) - 1)):
            if "black" in lines[i]:
                bs=re.search(r'black_start: *(\d+\.\d+).*$', lines[i])
                be=re.search(r'.*black_end: *(\d+\.\d+).*$', lines[i])
                if bs and be and cumulative_runtime -180 <= float(bs.group(1)) <= 180 + cumulative_runtime:
                    ep_end_offset = float(bs.group(1)) - cumulative_runtime
                    chapters[chap_ep-1]['end'] += ep_end_offset
                    episode_runtimes[chap_ep-1] += ep_end_offset
                    chap_start=min(cumulative_runtime + ep_end_offset, float(be.group(1)))
                    if float(be.group(1)) - chap_start < 30: chap_start = float(be.group(1))
                    break
        chap_ep += 1
        chapters.append({"start": chap_start})

    if "end" not in chapters['chap_ep']:
        chapters[chap_ep].update({"end": duration})
    if chap_ep == 1:
        logger.info("no chapters found based on tmdb lookup, '{}'".format(srcpath))
    else:
        logger.info("Chapters derived from tmdb lookup, '{}' chapters, '{}' episodes in file '{}'".format(chap_ep, last_episode - first_episode + 1))

    if chap_ep > 1:
        print_chap_file(tmp_dir, chapters, first_episode, chap_ep)
        r = subprocess.run(['mkvpropedit', cache_file, '--chapters', tmp_dir + 'chapters.xml'], capture_output=True)
        return [True]

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
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get the path to the file
    abspath = data.get('file_in')
    outpath = data.get('file_out')
    srcpath = data.get('original_file_path')
    duration = float(ffmpeg.probe(srcpath)["format"]["duration"])

    # Set up cache working directory
    split_hash = hashlib.md5(os.path.basename(srcpath).encode('utf8')).hexdigest()
    tmp_dir = os.path.join('/tmp/unmanic/', '{}'.format(split_hash)) + '/'
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    split_base, split_base_noext, sfx = get_split_details(srcpath)
    match = re.search(r'.*(S\d+[ -]*E\d+ *- *E*\d+).*$', split_base_noext)
    if not match:
        logger.info("File name does not indicate presence of multiple episodes. Aborting")
        return data

    split_method = settings.get_setting('split_method')

    if split_method == 'chapters' or split_method == 'combo':
        chapters = ffmpeg.probe(abspath, show_chapters=None)['chapters']
        if chapters:
            logger.info("Splitting file '{}' based on presence of '{}' chapters".format(abspath, len(chapters)))
        else:
            if split_method != 'combo':
                logger.info("No chapters found and split_method = chapters. Aborting")
                return data
    if split_method == 'combo' or split_method == 'time':
        n_episodes = get_last_episode(base_noext) - get_first_episode(base_noext) + 1
        chapter_time = duration / n_episodes
        logger.info("Splitting file '{}' based on chapter times of '{}' minutes".format(abspath, chapter_time))

    if split_method == 'sbi':
        chapters = get_chapters_from_sb_intervals(srcpath, tmp_dir, settings)
        if not chapters:
            logger.info("Chapters could not be identified from silence / black intervals '{}' - Aborting".format(abspath))
            return data
        else:
            logger.info("Splitting file '{}' based on identification of '{}' chapters using silence / black intervals".format(abspath, chapters))

    if split_method == 'tmdb':
        chapters = get_chapters_based_on_tmdb(srcpath, tmp_dir, settings)
        if not chapters:
            logger.info("Chapters could not be identified from tmdb lookup '{}' - Aborting".format(abspath))
            return data
        else:
            logger.info("Splitting file '{}' based on identification of '{}' chapters using tmdb lookup".format(abspath, chapters))

    # Construct command
    logger.debug("basename for split - no ext: '{}'".format(split_base_noext))
    match = re.search(r'(.*)(S\d+[ -]*E)\d+-E*\d+(.*$)', split_base_noext)

    if not match:
        raise Exception("Unable to find Season Episode string in source file name - unable to split file")
        return

    split_file = match.group(1) + match.group(2) + '%1d' + match.group(3) + sfx

    data['exec_command'] = ['mkvmerge']
    if split_method == 'chapters' or (split_method == 'combo' and chapters) or (split_method == 'sbi' and chapters) or (split_method == 'tmdb' and chapters):
        f = abspath
        if split_method == 'sbi' or split_method == 'tmdb': f = tmp_dir + split_base
        data['exec_command'] += ['-o', tmp_dir + split_file, '--split', 'chapters:all', f]
        return data
    if split_method == 'combo' or split_method == 'time':
        split_time = str(60 * int(chapter_time)) + 's'
        data['exec_command'] += ['-o', tmp_dir + split_file, '--split', split_time, abspath]
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
        # move files from temp dir in cache to destination dir
        logger.info("dest files: '{}'".format(data.get('destination_files')))
        srcpathbase = data.get('source_data')['basename']
        srcpathbase_no_ext = os.path.splitext(srcpathbase)[0]

        if data.get('library_id'):
            settings = Settings(library_id=data.get('library_id'))
        else:
            settings = Settings()

        season_dir= settings.get_setting('season_dir')
        keep_original = settings.get_setting('keep_original')

        # get starting episode number from multiepisode source
        first_episode = get_starting_episode(srcpathbase)
        if first_episode == -1:
            return

        # calculate offset - mkvmerge only numbers splits starting from 1
        ep_offset = 0
        if first_episode > 1:
            ep_offset = first_episode - 1
        split_hash = hashlib.md5(srcpathbase.encode('utf8')).hexdigest()
        tmp_dir = os.path.join('/tmp/unmanic/', '{}'.format(split_hash)) + '/'
        dest_file = data.get('destination_files')[0]
        dest_dir = os.path.split(dest_file)[0] + '/'

        # get season number for new directory if plugin configured for  that option
        if season_dir:
            match = re.search(r'.*S(\d+)[ -]*E\d+.*$', srcpathbase)
            match2 = re.search(r'(^.*)S\d+[ -]*E\d+-E*\d+(.*$)', srcpathbase_no_ext)

            if match and match2:
                season = match.group(1)
                st=match2.group(1) + match2.group(2)
                st=re.search(r'^\s*(.*$)\s*$', st)
                logger.debug("Season: '{}', Series Title: '{}'".format(season, st))
                if st:
                    st = st.group(1)
                else:
                    st = "title doesn't match pattern"
                if st != "title doesn't match pattern":
                    dest_dir += st + ' - ' + 'Season ' + season + '/'
                    try:
                        os.makedirs(dest_dir, mode=0o777)
                    except FileExistsError:
                        logger.info("Directory '{}' already exists - placing split files there".format(dest_dir))
                else:
                    logger.info("Sseries title doesn't match pattern - leaving split files in same directory as multiepisode file")
            else:
                logger.info("could not identify season number & / or series title - leaving split files in same directory as multiepisode file")

        logger.debug("dest_file: '{}', dest_dir: '{}'".format(dest_file, dest_dir))

        for f in glob.glob(tmp_dir + "/*.mkv"):
            if os.path.basename(f) == srcpathbase:
                continue
            match = re.search(r'.*S\d+[ -]*E(\d+).*$', f)
            if match:
                try:
                    episode = int(match.group(1))
                except ValueError:
                    raise ValueError('match didnt produce a valid episode number')
                    return

            # adjust episode numbers based on offset - offset is 0 if first episode is 1
            correct_episode = episode + ep_offset
            fdest = f.replace("E" + str(episode),"E" + str(correct_episode)) 
            fdest_base=os.path.split(fdest)[1]
            logger.debug("f: '{}', fdest: '{}'".format(f, fdest_base))
            shutil.copy2(f, dest_dir + fdest_base)

        # remove temp files and directory
        for ext in ['mkv', 'xml', 'log']:
            for f in glob.glob("*."+ext, root_dir=tmp_dir):
                os.remove(tmp_dir + f)
        shutil.rmtree(tmp_dir)
        if not keep_original:
          os.remove(data.get('source_data')['abspath'])
    return
