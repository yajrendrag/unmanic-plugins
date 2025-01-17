#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     17 Jan 2025(09:45 AM)

    Copyright:
        Unmanic plugin code Copyright (C) 2024, 2025 Jay Gardner
        PySceneDetect module code Copyright (C) 2024, Brandon Castellano

        Unmanic Code:
        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

        PySceneDetect:
        This Unmanic plugin module uses PySceneDetect (https://github.com/Breakthrough/PySceneDetect) which is governed by it's own
        license terms using BSD 3-Clause "New" or "Revised" License.  The text of this license has accompanied this program (PySceneDetectLICENSE).
        If for some reason you do not have it, please refer to <https://github.com/Breakthrough/PySceneDetect/blob/main/LICENSE>.

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
import numpy as np
from scenedetect import open_video, detect, SceneManager, ContentDetector
from scenedetect.detectors import ThresholdDetector
import cv2

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.plugins import PluginsHandler
from unmanic.libs.library import Library

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.split_mkv")

class Settings(PluginSettings):
    settings = {
        "split_method":          "tmdb",
        "tmdb_fine_tune":        "b",
        "season_dir":            True,
        "season_dir_format":     "choose format for Season directory name",
        "keep_original":         False,
        "min_silence":           "2",
        "min_black":             "3",
        "tmdb_api_key":              "enter your tmdb apikey",
        "tmdb_api_read_access_token":    "enter your tmdb api read access token",
        "window_size":           "3",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "split_method":        self.__set_split_method_form_settings(),
            "tmdb_fine_tune":      self.__set_tmdb_fine_tune_form_settings(),
            "season_dir":    {
                 "label":    "check this to create a new Season subdirectory in the folder containing the multi episode file is",
            },
            "season_dir_format":   self.__set_season_dir_format_form_settings(),
            "keep_original": {
                 "label":    "check this to keep the original multiepisode file, otherwise it is deleted",
            },
            "min_silence":         self.__set_min_silence_form_settings(),
            "min_black":           self.__set_min_black_form_settings(),
            "tmdb_api_key": self.__set_tmdb_api_key_form_settings(),
            "tmdb_api_read_access_token": self.__set_tmdb_api_read_access_token_form_settings(),
            "window_size":         self.__set_window_size_form_settings(),
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
                {
                    "value": 'credits',
                    "label": 'Create chapter marks based on looking up episode duration on tmdb and fine tuning with text search for credits',
                },
            ],
        }
        return values

    def __set_tmdb_fine_tune_form_settings(self):
        values = {
            "label":        "Enter Choice",
            "description":  "Choose black or silence/black overlap for the fine tuning used with tmdb episode duration lookup",
            "input_type": "select",
            "select_options": [
                {
                    "value": "b",
                    "label": "black",
                },
                {
                    "value": "sb",
                    "label": "silence/black overlap",
                },
            ],
        }
        if self.get_setting('split_method') != 'tmdb':
            values["display"] = 'hidden'
        return values

    def __set_season_dir_format_form_settings(self):
        values = {
            "label":          "Enter Choice",
            "description":    "Format for Season directory name",
            "input_type":     "select",
            "select_options": [
                {
                    "value": "series_title_SxxEyy_dash_rez_dash_qual",
                    "label": "a folder named 'Series Title SxxEyy - resolution - quality': resolution and quality will only be included if they are in the multiepisode filename",
                },
                {
                    "value": "season_n",
                    "label": "a folder named 'Season N', where N is the season number extracted from the source file name",
                },
                {
                    "value": "series_title_dash_season_n",
                    "label": "a folder named 'Series Title - Season N'",
                },
                {
                    "value": "season_n_dash_series_title",
                    "label": "a folder named 'Season N - Series Title'",
                },
            ],

        }
        if not self.get_setting('season_dir'):
            values["display"] = 'hidden'
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
        if self.get_setting('split_method') == 'sbi':
            return values
        if (self.get_setting('split_method') == 'tmdb' and self.get_setting('tmdb_fine_tune') != 'sb'):
            values["display"] = 'hidden'
        if self.get_setting('split_method') == 'chapters' or self.get_setting('split_method') == 'time' or self.get_setting('split_method') == 'combo' or self.get_setting('split_method') == 'credits':
            values["display"] = 'hidden'
        return values

    def __set_min_black_form_settings(self):
        values = {
            "label":          "Time",
            "description":    "Minimum time for a black screen scene detection interval to identify an episode change",
            "input_type":     "slider",
            "slider_options": {
                "min": 1,
                "max": 10,
                "step": 0.1
            }
        }
        if self.get_setting('split_method') == 'chapters' or self.get_setting('split_method') == 'time' or self.get_setting('split_method') == 'combo' or self.get_setting('split_method') == 'credits':
            values["display"] = 'hidden'
        if self.get_setting('split_method') == 'sbi' or self.get_setting('split_method') == 'tmdb' or self.get_setting('split_method') == 'credits':
            return values
        return values

    def __set_tmdb_api_key_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api key",
            "input_type": "textarea",
        }
        if self.get_setting('split_method') != 'tmdb' and self.get_setting('split_method') != 'credits':
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_read_access_token_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api api read access token",
            "input_type": "textarea",
        }
        if self.get_setting('split_method') != 'tmdb' and self.get_setting('split_method') != 'credits':
            values["display"] = 'hidden'
        return values

    def __set_window_size_form_settings(self):
        values = {
            "label":          "Time",
            "description":    "Number of minutes before and after the tmdb lookup to search for credit text - 3 is a good starting point",
            "input_type":     "slider",
            "slider_options": {
                "min": 1,
                "max": 12,
                "step": .1
            }
        }
        if self.get_setting('split_method') != 'credits':
            values["display"] = 'hidden'
        return values

class my_library(Library):
    {
    }

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

    library_id = data.get('library_id')

    basename = os.path.split(abspath)[1]
    base_noext = os.path.splitext(basename)[0]
    duration = float(ffmpeg.probe(abspath)["format"]["duration"])

    parsed_info = PTN.parse(basename, standardise=False)

    try:
        episodes = parsed_info['episode']
    except KeyError:
        episodes = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))
        raise Exception("Unaable to parse episode range from multiepisode file name")
        return data

    first_episode, last_episode = get_first_and_last_episodes(episodes)
    n_episodes = last_episode - first_episode + 1

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

def get_first_and_last_episodes(episodes):
    if type(episodes) == list:
        first_episode = episodes[0]
        last_episode = episodes[len(episodes) -1]
    elif type(episodes) == int:
        first_episode = episodes
        last_episode = episodes
    else:
        logger.error("Episodes not successfully parsed from video file: '{}'".format(srcpath))
        raise Exception("Episodes not successfully parsed")
        return
    return first_episode, last_episode

def dur2hms(dur):
     h = int(dur/3600)
     rdurm = dur - h*3600
     m = int(rdurm/60)
     s = rdurm - m*60
     return f"{h:02d}:{m:02d}:{s:06.3f}"

def prep_sb_file(srcpath, tmp_dir, split_base, split_base_noext, cache_file, settings):
    # analyze file and find silence and black screen intervals
    b_detect_int = settings.get_setting('min_black')
    s_detect_int = settings.get_setting('min_silence')
    split_method = settings.get_setting('split_method')
    if split_method == 'tmdb':
        tmdb_fine_tune = settings.get_setting('tmdb_fine_tune')
    else:
        tmdb_fine_tune = ''
    dlog=open(tmp_dir + 'detection.log', 'w', encoding='utf-8')
    if (split_method == 'tmdb' and tmdb_fine_tune == 'sb') or split_method == 'sbi':
        logger.info(f"Capturing silence/black scene intervals from {srcpath}")
        r=subprocess.run(['ffmpeg', '-progress', 'pipe:1', '-v', 'quiet', '-loglevel', 'info', '-i', srcpath, '-vf', 'blackdetect=d=' + str(b_detect_int) + ':pix_th=0.1', '-af', 'silencedetect=n=-50dB:d=' + str(s_detect_int), '-f', 'null', '-'], stderr=dlog, stdout=dlog)
    else:
        logger.info(f"Capturing black scene intervals from {srcpath}")
        r=subprocess.run(['ffmpeg', '-progress', 'pipe:1', '-v', 'quiet', '-loglevel', 'info', '-i', srcpath, '-vf', 'blackdetect=d=' + str(b_detect_int) + ':pix_th=0.1', '-f', 'null', '-'], stderr=dlog, stdout=dlog)
    if r.returncode > 0:
        logger.error("Unable to black scenes &/or silence/black overlap scenes in '{}' - aborting".format(srcpath))
        raise Exception("Scene detection Error")
        return
    dlog.close()
    logger.info(f"Completed capture of silence/black scenes from {srcpath}")
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

def get_parsed_info(split_base):
    split_base_proxy = ""
    #m=re.search(r'^.*(\[*)E\d+ *[-_]E*\d+(\]*).*$', split_base)
    m=re.search(r'^.*S\d+ *(\[)*E\d+ *[-_]E*\d+(\])*.*$', split_base)
    #m=re.search(r'^.*(\[)E\d+ *-E*\d+(\]).*$', split_base)
    if m:
        #split_base_proxy = re.sub(r'(^.*)\[(E\d+ *-E*\d+)\](.*$)', r'\1\2\3',split_base)
        #split_base_proxy = re.sub(r'(^.*)\[(E\d+ *)[-_](E*\d+)\](.*$)', r'\1\2-\3\4',split_base)
        split_base_proxy = re.sub(r'(^.*S\d+ *)\[*(E\d+ *)[-_](E*\d+)\]*(.*$)', r'\1\2-\3\4',split_base)
    if split_base_proxy:
        parsed_info = PTN.parse(split_base_proxy, standardise=False)
    else:
        parsed_info = PTN.parse(split_base, standardise=False)
    return parsed_info

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

def sb_analyze(lines, i):
        if "silence" in lines[i] and "black" in lines[i+1]:
            ss=re.search(r'silence_start: (\d+\.\d+).*$', lines[i])
            se=re.search(r'.*silence_end: (\d+\.\d+).*$', lines[i])
            try:
                silence=(float(ss.group(1)), float(se.group(1)))
            except AttributeError:
                silence = ()
            bs=re.search(r'black_start: *(\d+\.\d+).*$', lines[i+1])
            be=re.search(r'.*black_end: *(\d+\.\d+).*$', lines[i+1])
            try:
                black=(float(bs.group(1)), float(be.group(1)))
            except AttributeError:
                black = ()
            return silence, black
        elif "black" in lines[i] and "silence" in lines[i+1]:
            bs=re.search(r'black_start: *(\d+\.\d+).*$', lines[i])
            be=re.search(r'.*black_end: *(\d+\.\d+).*$', lines[i])
            try:
                black=(float(bs.group(1)), float(be.group(1)))
            except AttributeError:
                black = ()
            ss=re.search(r'silence_start: (\d+\.\d+).*$', lines[i+1])
            se=re.search(r'.*silence_end: (\d+\.\d+).*$', lines[i+1])
            try:
                silence=(float(ss.group(1)), float(se.group(1)))
            except AttributeError:
                silence = ()
            return silence, black
        return (),()

def get_chapters_from_sb_intervals(srcpath, duration, tmp_dir, settings):
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
    prep_sb_file(srcpath, tmp_dir, split_base, split_base_noext, cache_file, settings)

    # analyze parsed detection log into chapter start/end times on which chapters will be formed
    intervals=open(tmp_dir + 'det.log', 'rt', encoding='utf-8')
    lines=intervals.readlines()
    intervals.close()

    # get starting episode number
    parsed_info = get_parsed_info(split_base)

    try:
        episodes = parsed_info['episode']
    except KeyError:
        episodes = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))
        raise Exception("Unaable to parse episode range from multiepisode file name")
        return data

    first_episode, last_episode = get_first_and_last_episodes(episodes)

    chapters = []
    chap_ep = 1
    chapters.append({"start": 0.0})
    logger.debug("first_episode: '{}', last_episode: '{}'".format(first_episode, last_episode))

    # find chapter start / end times based on silence and black detected intervals
    for i in range((len(lines) - 1)):
        if ("silence" in lines[i] and "silence" in lines[i+1]) or ("black" in lines[i] and "black" in lines[i+1]):
            continue
        silence, black = sb_analyze(lines, i)
        if silence == () or black == ():
            continue
        logger.debug("chap_ep: '{}'".format(chap_ep))
        overlap = get_overlap(silence, black)
        logger.debug("overlap: '{}'".format(overlap))
        if overlap and i < len(lines) - 1:
            logger.debug("Overlap of '{}' seconds on interval '{}' betweeen silence and black intervals, high confidence interval represents a new episode.  Video: '{}'".format(overlap, i/2+1, split_base_noext))
            chap_start = float(max(silence[1], black[1]))
            chap_end = float(min(silence[0], black[0]))
            chapters[chap_ep-1].update({"end": chap_end})
            chap_ep += 1
            chapters.append({"start": chap_start})
        logger.debug("chapters: '{}'".format(chapters))
    if "end" not in chapters[chap_ep-1]:
        chapters[chap_ep-1].update({"end": duration})
    logger.debug("chapters: '{}'".format(chapters))
    if chap_ep == 1:
        logger.info("no chapters found based on silence/black scene detection mode, '{}'".format(srcpath))
    else:
        logger.info("Chapters derived from silence/black scene changes, '{}' chapters, '{}' episodes in file '{}'".format(chap_ep, last_episode - first_episode + 1, srcpath))

    if chap_ep > 1:
        print_chap_file(tmp_dir, chapters, first_episode, chap_ep)
        r = subprocess.run(['mkvpropedit', cache_file, '--chapters', tmp_dir + 'chapters.xml'], capture_output=True)
        return [True]

def get_chapters_based_on_tmdb(srcpath, duration, tmp_dir, settings):
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

    tmdb_fine_tune = settings.get_setting('tmdb_fine_tune')
    prep_sb_file(srcpath, tmp_dir, split_base, split_base_noext, cache_file, settings)

    tmdb_api_key = settings.get_setting("tmdb_api_key")
    tmdb_api_read_access_token = settings.get_setting("tmdb_api_read_access_token")
    tmdburl = 'https://api.themoviedb.org/3/search/tv?query='
    tmdb_season_url = 'https://api.themoviedb.org/3/tv/'
    headers = {'accept': 'application/json', 'Authorization': 'Bearer ' + tmdb_api_read_access_token}

    parsed_info = get_parsed_info(split_base)

    try:
        title = parsed_info["title"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(srcpath))
        raise Exception("Unable to parse Series Title from multiepisode file name")
        return False

    try:
        episodes = parsed_info['episode']
    except KeyError:
        episodes = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))
        raise Exception("Unable to parse episode range from multiepisode file name")
        return False

    first_episode, last_episode = get_first_and_last_episodes(episodes)

    try:
        season = parsed_info["season"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(srcpath))
        raise Exception("Unable to parse Season from multiepisode file name")
        return False

    vurl = tmdburl + title + '&api_key=' + tmdb_api_key
    try:
        video = requests.request("GET", vurl, headers=headers)
        id = video.json()["results"][0]['id']
    except:
        logger.error("Error requesting video info from tmdb. Aborting")
        raise Exception(f"Unable to find video {srcpath} in tmdb")
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
            if tmdb_fine_tune == 'sb':
                if ("silence" in lines[i] and "silence" in lines[i+1]) or ("black" in lines[i] and "black" in lines[i+1]):
                    continue
                silence, black = sb_analyze(lines, i)
                if silence == () or black == ():
                    continue
                overlap = get_overlap(silence, black)
                if overlap and i < len(lines) - 1:
                    logger.debug("Overlap of '{}' seconds on interval '{}' betweeen silence and black intervals - test if interval near episode from lookup.  Video: '{}'".format(overlap, i/2+1, split_base_noext))
                    interval_end = float(max(silence[1], black[1]))
                    interval_start = float(min(silence[0], black[0]))
                    logger.debug(f"cumulative runtime - 180: {cumulative_runtime -180}, interval start: {interval_start}, interval end: {interval_end}; cumulative runtime + 180: {cumulative_runtime + 180}; total cumulative runtime: {cumulative_runtime}")
                    if interval_start and interval_end and (cumulative_runtime - 180 <= interval_start <= interval_end <= 180 + cumulative_runtime):
                        logger.debug(f"cumulative runtime - 180: {cumulative_runtime -180}, interval start: {interval_start}, interval end: {interval_end}; cumulative runtime + 180: {cumulative_runtime + 180}; total cumulative runtime: {cumulative_runtime}")
                        ep_end_offset = interval_end - cumulative_runtime
                        chapters[chap_ep-1]['end'] += ep_end_offset
                        episode_runtimes[chap_ep-1] += ep_end_offset
                        chap_start=min(cumulative_runtime + ep_end_offset, interval_end)
                        if interval_end - chap_start < 30: chap_start = interval_end
                        logger.debug(f"chapters[chap_ep-1]['end']: {chapters[chap_ep-1]['end']}; chap_start: {chap_start}")
                        break
            else:
                if "black" in lines[i]:
                    i_s = re.search(r'black_start: *(\d+\.\d+).*$', lines[i])
                    if i_s: interval_start = float(i_s.group(1))
                    i_e = re.search(r'.*black_end: *(\d+\.\d+).*$', lines[i])
                    if i_e: interval_end = float(i_e.group(1))
                    if i_s and i_e and (cumulative_runtime - 180 <= interval_start <= interval_end <= 180 + cumulative_runtime):
                        logger.debug(f"cumulative runtime - 180: {cumulative_runtime -180}, interval start: {interval_start}, interval end: {interval_end}; cumulative runtime + 180: {cumulative_runtime + 180}; total cumulative runtime: {cumulative_runtime}")
                        ep_end_offset = interval_end - cumulative_runtime
                        chapters[chap_ep-1]['end'] += ep_end_offset
                        episode_runtimes[chap_ep-1] += ep_end_offset
                        chap_start=min(cumulative_runtime + ep_end_offset, interval_end)
                        if interval_end - chap_start < 30: chap_start = interval_end
                        break
        chap_ep += 1
        chapters.append({"start": chap_start})

    if "end" not in chapters[chap_ep-1]:
        chapters[chap_ep-1].update({"end": duration})
    if chap_ep == 1:
        logger.info("no chapters found based on tmdb lookup, '{}'".format(srcpath))
    else:
        logger.info("Chapters derived from tmdb lookup, '{}' chapters, '{}' episodes in file '{}'".format(chap_ep, last_episode - first_episode + 1, srcpath))

    if chap_ep > 1:
        print_chap_file(tmp_dir, chapters, first_episode, chap_ep)
        r = subprocess.run(['mkvpropedit', cache_file, '--chapters', tmp_dir + 'chapters.xml'], capture_output=True)
        return [True]

def get_credits_start_and_end(video_path, tmp_dir, window_start, window_size, width, height):

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    userdata = settings.get_profile_directory()

    # get video frame rate from ffprobe
    frs = ffmpeg.probe(video_path)["streams"][0]['r_frame_rate']
    if '/' in frs:
        fr = int(frs.split('/')[0])/int(frs.split('/')[1])
    else:
        fr = int(frs)

    # get video scenes using PySceneDetect - assume minimum scene length is 30 seconds 
    # seek to start of episode window start and collect 6 minutes of frames
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ThresholdDetector(threshold=15, min_scene_len=int(fr*30)))
    video.seek(float(window_start))
    scene_manager.detect_scenes(video, duration=float(window_size)*2*60)
    scene_list = scene_manager.get_scene_list()
    if not scene_list:
        logger.debug(f"Scene list is empty - move to next episode")
    else:
        for s in scene_list:
            logger.debug(f"scene list: {s}")

    # extract collected frames and write to /tmp/unmanic cache
    fout='%06d.png'
    for i in range(len(scene_list)):
        command = ['ffmpeg', '-hwaccel', 'cuda', '-hwaccel_output_format', 'nv12', '-ss', str(scene_list[i][0].get_seconds()), '-to', str(scene_list[i][1].get_seconds()), '-i', video_path, '-vf', f"crop={width}:{height-100}:0:100,fps=1/1", '-start_number', str(scene_list[i][0].get_frames()), tmp_dir + fout]
        r=subprocess.run(command, capture_output=True)
        if r.returncode != 0:
            logger.debug(f"stderr: {r.stderr.decode()}")
            logger.debug(f"Failed to find a valid scene - moving to next episode")
            return '',''

    # perform OCR on captured frames and write to text file
    os.environ["TESSDATA_PREFIX"] = f"/usr/share/tesseract-ocr/5/tessdata"
    pngfiles=glob.glob(tmp_dir + '/*.png')
    for pngfile in pngfiles:
        pngnum = re.search(r'(\d\d\d\d\d\d).png', pngfile)
        try:
            n=pngnum.group(1)
        except:
            logger.debug(f"pngfiles: {pngfiles}")
            logger.debug(f"Failed to find pngfile - moving to next episode")
            return '',''
        subprocess.run(['tesseract', pngfile, tmp_dir+"check_" + str(n)], capture_output=True)

    # using credits_dictionary (/config/credits_dictionary) find first file in scenes with text matching any words in credits dictionary
    # and identify the last file of the credits as that file which has '©' symbol signifying the video's copyright (typically on the last screen of credits)
    file_list = []
    copyright = ''
    cr_dict = userdata + '/credits_dictionary'
    with open(cr_dict) as cw:
        cwords = cw.read().splitlines()

    for f in glob.glob(tmp_dir + 'check*.txt'):
        with open(f) as file:
            strings = file.read()
            for w in cwords:
                if w in strings.lower():
                    file_list.append(f)
                    if w == '©': copyright=f
                    break

    file_list.sort()
    checkfiles = glob.glob(tmp_dir + 'check*.txt')
    checkfiles.sort()
    try:
        firstfile = [i for i in range(len(checkfiles)) if checkfiles[i] == file_list[0]][0]
    except:
        firstfile = ''
    try:
        lastfile = [i for i in range(len(checkfiles)) if checkfiles[i] == copyright][0]
    except:
        lastfile = ''

    # abort if firstfile or lastfile is '' - means it could not find start or end of credits in window
    if  lastfile == '' or firstfile == '':
        logger.debug(f"did not find credit start or end in window - move to next episode")
        return '',''

    # Adjust lastfile to last frame containing '©' within 3 frames after first found:
    for adjacent in range(lastfile,lastfile+3):
        try:
            with open(checkfiles[adjacent], 'r') as f:
                strings = f.read()
                if '©' in strings.lower(): copyright=checkfiles[adjacent]
        except IndexError:
            break

    # Adjust firstfile to first frame containing text within 4 frames prior to first cword found:
    for adjacent in range(firstfile, firstfile-4, -1):
        if os.stat(checkfiles[adjacent]).st_size > 0:
            firstfile = adjacent
        else:
            break

    for f in pngfiles:
        os.remove(f)
    for f in checkfiles:
        os.remove(f)

    return firstfile, lastfile

def get_chapters_from_credits(srcpath, duration, tmp_dir, settings):
    """
    lookup episode duration on tmdb. fine tune with text search for credit text.
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

    tmdb_api_key = settings.get_setting("tmdb_api_key")
    tmdb_api_read_access_token = settings.get_setting("tmdb_api_read_access_token")
    tmdburl = 'https://api.themoviedb.org/3/search/tv?query='
    tmdb_season_url = 'https://api.themoviedb.org/3/tv/'
    headers = {'accept': 'application/json', 'Authorization': 'Bearer ' + tmdb_api_read_access_token}
    window_size = settings.get_setting("window_size")

    parsed_info = get_parsed_info(split_base)

    try:
        title = parsed_info["title"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(srcpath))
        raise Exception("Unable to parse Series Title from multiepisode file name")
        return False

    try:
        episodes = parsed_info['episode']
    except KeyError:
        episodes = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))
        raise Exception("Unable to parse episode range from multiepisode file name")
        return False

    first_episode, last_episode = get_first_and_last_episodes(episodes)

    try:
        season = parsed_info["season"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(srcpath))
        raise Exception("Unable to parse Season from multiepisode file name")
        return False

    vurl = tmdburl + title + '&api_key=' + tmdb_api_key
    try:
        video = requests.request("GET", vurl, headers=headers)
        id = video.json()["results"][0]['id']
    except:
        logger.error("Error requesting video info from tmdb. Aborting")
        raise Exception(f"Unable to find video {srcpath} in tmdb")
        return False

    chapters = []
    chap_ep = 1
    chapters.append({"start": 0.0})
    episode_runtimes = []
    stream=[s['index'] for s in ffmpeg.probe(cache_file)['streams'] if s['codec_type'] == 'video']
    if stream:
        width = ffmpeg.probe(cache_file)['streams'][stream[0]]['width']
        height = ffmpeg.probe(cache_file)['streams'][stream[0]]['height']
    else:
        logger.error(f"Cannot find video stream in file {cache_file} to extract width and height - aborting")
        return False
    for episode in range(first_episode, last_episode):
        show_url = tmdb_season_url + str(id) + '/season/' + str(season) + '/episode/' + str(episode)
        episode_result = requests.request("GET", show_url, headers=headers)
        episode_duration = float(episode_result.json()['runtime'])
        episode_runtimes.append(episode_duration * 60.0)
        cumulative_runtime = sum(float(i) for i in episode_runtimes)
        chapters[chap_ep-1].update({"end": cumulative_runtime})
        chap_start = cumulative_runtime + 1
        window_start = str(int(cumulative_runtime - window_size*60))
        window_end = str(int(cumulative_runtime + window_size*60))

        firstfile, lastfile = get_credits_start_and_end(cache_file, tmp_dir, window_start, window_size, width, height)

        if firstfile and lastfile:
            frame_credit_start = int(firstfile)
            frame_credit_end = int(lastfile)
            time_credit_start = frame_credit_start*1 + int(window_start)
            time_credit_end = frame_credit_end*1 + int(window_start)
            chapters[chap_ep-1]['end'] = time_credit_end
            delta = time_credit_end - cumulative_runtime
            logger.debug(f"credits in episode {episode} start at {time_credit_start} and end at {time_credit_end} in file {srcpath}")
            episode_runtimes[chap_ep-1] += delta
            chap_start = time_credit_end + 1
        chap_ep += 1
        chapters.append({"start": chap_start})
        logger.debug(f"current chapters: {chapters}")

    if "end" not in chapters[chap_ep-1]:
        chapters[chap_ep-1].update({"end": duration})
    logger.debug(f"final chapters: {chapters}")
    if chap_ep == 1:
        logger.info("no chapters found based on tmdb lookup, '{}'".format(srcpath))
    else:
        logger.info("Chapters derived from tmdb lookup, '{}' chapters, '{}' episodes in file '{}'".format(chap_ep, last_episode - first_episode + 1, srcpath))

    if chap_ep > 1:
        print_chap_file(tmp_dir, chapters, first_episode, chap_ep)
        r = subprocess.run(['mkvpropedit', cache_file, '--chapters', tmp_dir + 'chapters.xml'], capture_output=True)
        return [True]
    else:
        return [False]


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
    parsed_info = get_parsed_info(split_base)

    try:
        episodes = parsed_info['episode']
    except KeyError:
        episodes = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))
        raise Exception("Unable to parse episode range from multiepisode file name")
        return data

    if type(episodes) != list:
        logger.info("File name does not indicate presence of multiple episodes. Aborting")
        return data

    first_episode, last_episode = get_first_and_last_episodes(episodes)

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
        n_episodes = last_episode - first_episode + 1
        chapter_time = duration / n_episodes
        logger.info("Splitting file '{}' based on chapter times of '{}' minutes".format(abspath, chapter_time))

    if split_method == 'sbi':
        chapters = get_chapters_from_sb_intervals(srcpath, duration, tmp_dir, settings)
        if not chapters:
            logger.info("Chapters could not be identified from silence / black intervals '{}' - Aborting".format(abspath))
            return data
        else:
            logger.info("Splitting file '{}' based on identification of '{}' chapters using silence / black intervals".format(abspath, chapters))

    if split_method == 'tmdb':
        chapters = get_chapters_based_on_tmdb(srcpath, duration, tmp_dir, settings)
        if not chapters:
            logger.info("Chapters could not be identified from tmdb lookup '{}' - Aborting".format(abspath))
            return data
        else:
            logger.info("Splitting file '{}' based on identification of '{}' chapters using tmdb lookup".format(abspath, chapters))

    if split_method == 'credits':
        chapters = get_chapters_from_credits(srcpath, duration, tmp_dir, settings)
        if not chapters:
            logger.info("Chapters could not be identified from tmdb lookup '{}' - Aborting".format(abspath))
            return data
        else:
            logger.info("Splitting file '{}' based on identification of '{}' chapters using tmdb lookup".format(abspath, chapters))

    # Construct command
    logger.debug("basename for split - no ext: '{}'".format(split_base_noext))
    # match = re.search(r'(.*)(S\d+[ -]*E)\d+-E*\d+(.*$)', split_base_noext)
    try:
        title = parsed_info['title']
    except KeyError:
        title = ""
        logger.error("Error parsing episode list from file: '{}'".format(srcpath))
        raise Exception("Unable to parse title from multiepisode file name")
        return

    try:
        resolution = parsed_info['resolution']
    except KeyError:
        resolution = ""
        logger.info("Error parsing resolution from from file: '{}' - split files will not containe resolution in filename".format(srcpath))

    try:
        quality = parsed_info['quality']
    except KeyError:
        quality = ""
        logger.info("Error parsing quality from from file: '{}'; split files will not containe quality in filename".format(srcpath))

    try:
        codec = parsed_info['codec']
    except KeyError:
        codec = ""
        logger.info("Error parsing codec name from from file: '{}'; split files will not containe codec name in filename".format(srcpath))

    # split_file = match.group(1) + match.group(2) + '%1d' + match.group(3) + sfx
    split_file = parsed_info["title"] + ' S' + str(parsed_info["season"]) +'E' + '%d'
    if resolution: split_file += ' - ' + resolution
    if quality: split_file += ' - ' + quality
    if codec: split_file += ' - ' + codec
    split_file += sfx

    data['exec_command'] = ['mkvmerge']
    if split_method == 'chapters' or (split_method == 'combo' and chapters) or (split_method == 'sbi' and chapters) or (split_method == 'tmdb' and chapters) or (split_method == 'credits' and chapters):
        f = abspath
        if split_method == 'sbi' or split_method == 'tmdb' or split_method == 'credits': f = tmp_dir + split_base
        data['exec_command'] += ['-o', tmp_dir + split_file, '--split', 'chapters:all', f]
        return data
    if split_method == 'combo' or split_method == 'time':
        split_time = str(60 * int(chapter_time)) + 's'
        data['exec_command'] += ['-o', tmp_dir + split_file, '--split', split_time, abspath]
        return data

    data['file_out'] = None

def on_postprocessor_file_movement(data):
    """
    Runner function - configures additional postprocessor file movements during the postprocessor stage of a task.

    The 'data' object argument includes:
        source_data             - Dictionary containing data pertaining to the original source file ('abspath' and 'basename').
        remove_source_file      - Boolean, should Unmanic remove the original source file after all copy operations are complete.
        copy_file               - Boolean, should Unmanic run a copy operation with the returned data variables.
        file_in                 - The converted cache file to be copied by the postprocessor.
        file_out                - The destination file that the file will be copied to.
        run_default_file_copy   - Whether Unmanic should perform the default file copy.

    :param data:
    :return:
    """

    data['run_default_file_copy'] = False
    return

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
        srcpath = data.get('source_data')['abspath']

        library_id = data.get('library_id')
        lib_id = my_library(library_id).get_id()
        lib_plugins = my_library(library_id).get_enabled_plugins(include_settings=True)
        logger.debug(f"lib_plugins: {lib_plugins}")
        lib_path = my_library(library_id).get_path()
        mover2_path = ''
        for i in range(len(lib_plugins)):
            if lib_plugins[i]['plugin_id'] == 'mover2':
                mover2_path = lib_plugins[i]['settings']['destination_directory']
                mover2_recreate_directory_structure = lib_plugins[i]['settings']['recreate_directory_structure']
                mover2_include_library_structure = lib_plugins[i]['settings']['include_library_structure']
                logger.debug(f"Switching file path from {lib_path} to {mover2_path}")
                logger.debug(f"mover2_include_library_structure: {mover2_include_library_structure}; mover2_recreate_directory_structure: {mover2_recreate_directory_structure}")
                break

        parsed_info = get_parsed_info(srcpathbase)

        try:
            episodes = parsed_info["episode"]
        except KeyError:
            episode = ""
            logger.error("Error parsing episodes from file: '{}'".format(srcpathbase))

        try:
            season = parsed_info["season"]
        except KeyError:
            season = ""
            logger.error("Error parsing season from file: '{}'".format(srcpathbase))

        try:
            title = parsed_info["title"]
        except KeyError:
            title = ""
            logger.error("Error parsing title from file: '{}'".format(srcpathbase))

        try:
            resolution = parsed_info['resolution']
        except KeyError:
            resolution = ""
            logger.info("Error parsing resolution from from file: '{}' - season folder will not contain resolution in name".format(srcpathbase))

        try:
            quality = parsed_info['quality']
        except KeyError:
            quality = ""
            logger.info("Error parsing qaulity from from file: '{}'; season folder will not contain quality in name".format(srcpathbase))


        if data.get('library_id'):
            settings = Settings(library_id=data.get('library_id'))
        else:
            settings = Settings()

        season_dir= settings.get_setting('season_dir')
        if season_dir:
            season_dir_format = settings.get_setting('season_dir_format')
        keep_original = settings.get_setting('keep_original')

        # get starting episode number from multiepisode source
        first_episode, last_episode = get_first_and_last_episodes(episodes)

        # calculate offset - mkvmerge only numbers splits starting from 1
        ep_offset = 0
        if first_episode > 1:
            ep_offset = first_episode - 1
        split_hash = hashlib.md5(srcpathbase.encode('utf8')).hexdigest()
        tmp_dir = os.path.join('/tmp/unmanic/', '{}'.format(split_hash)) + '/'
        dest_file = srcpath
        #dest_file = data.get('destination_files')[0]
        #dest_dir = os.path.split(dest_file)[0] + '/'
        dest_dir = os.path.split(srcpath)[0] + '/'
        logger.debug(f"srcpath: {srcpath}")
        logger.debug(f"dest_dir: {dest_dir}")
        if mover2_path:
            if mover2_include_library_structure:
                dest_dir = mover2_path + dest_dir
            elif mover2_recreate_directory_structure:
                dest_dir = dest_dir.replace(lib_path, mover2_path)
            else:
                dest_dir = mover2_path
            logger.debug(f"dest_dir: {dest_dir}")

        # get season number for new directory if plugin configured for  that option
        if season_dir:
            if season_dir_format == 'season_n_dash_series_title':
                dest_dir += 'Season '+str(season) + ' - ' + title + '/'
            elif season_dir_format == 'series_title_dash_season_n':
                dest_dir += title + ' - ' + 'Season '+str(season) + '/'
            elif season_dir_format == 'season_n':
                dest_dir += 'Season '+str(season) + '/'
            elif season_dir_format == 'series_title_SxxEyy_dash_rez_dash_qual':
                dest_dir +=  title + ' S' + str(season) + 'E' + str(first_episode) + '-' + 'E' + str(last_episode)
                if resolution: dest_dir += ' - ' + resolution
                if quality: dest_dir += ' - ' + quality
                dest_dir += '/'

            try:
                os.makedirs(dest_dir, mode=0o777)
            except FileExistsError:
                logger.info("Directory '{}' already exists - placing split files there".format(dest_dir))

        if not title:
            logger.info("Series title doesn't match pattern - leaving split files in same directory as multiepisode file")
        if not first_episode or not last_episode:
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
        for ext in ['mkv', 'xml', 'log', 'png', 'txt']:
            for f in glob.glob("*."+ext, root_dir=tmp_dir):
                os.remove(tmp_dir + f)
        shutil.rmtree(tmp_dir)
        if not keep_original:
          os.remove(data.get('source_data')['abspath'])
    return
