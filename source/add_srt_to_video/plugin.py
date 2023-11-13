#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     8 Nov 2023, (2:15 PM)
 
    Copyright:
        Copyright (C) 2023 Jay Gardner

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
import glob
import difflib

from unmanic.libs.unplugins.settings import PluginSettings

from add_srt_to_video.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.srt_to_video")

lang_codes = [('aa', 'aar'), ('ab', 'abk'), ('af', 'afr'), ('ak', 'aka'), ('am', 'amh'), ('ar', 'ara'), ('an', 'arg'), ('as', 'asm'), ('av', 'ava'), ('ae', 'ave'), ('ay', 'aym'), ('az', 'aze'), ('ba', 'bak'), ('bm', 'bam'), ('be', 'bel'), ('bn', 'ben'), ('bi', 'bis'), ('bo', 'bod / tib*'),
              ('bs', 'bos'), ('br', 'bre'), ('bg', 'bul'), ('ca', 'cat'), ('cs', 'ces / cze*'), ('ch', 'cha'), ('ce', 'che'), ('cn', 'zho / chi*'), ('cu', 'chu'), ('cv', 'chv'), ('kw', 'cor'), ('co', 'cos'), ('cr', 'cre'), ('cy', 'cym / wel*'), ('da', 'dan'), ('de', 'deu / ger*'), ('dv', 'div'), ('dz', 'dzo'),
              ('el', 'ell / gre*'), ('en', 'eng'), ('eo', 'epo'), ('et', 'est'), ('eu', 'eus / baq*'), ('ee', 'ewe'), ('fo', 'fao'), ('fa', 'fas / per*'), ('fj', 'fij'), ('fi', 'fin'), ('fr', 'fra / fre*'), ('fy', 'fry'), ('ff', 'ful'), ('gd', 'gla'), ('ga', 'gle'), ('gl', 'glg'), ('gv', 'glv'),
              ('gn', 'grn'), ('gu', 'guj'), ('ht', 'hat'), ('ha', 'hau'), ('he', 'heb'), ('hz', 'her'), ('hi', 'hin'), ('ho', 'hmo'), ('hr', 'hrv'), ('hu', 'hun'), ('hy', 'hye / arm*'), ('ig', 'ibo'), ('io', 'ido'), ('ii', 'iii'), ('iu', 'iku'), ('ie', 'ile'), ('ia', 'ina'), ('id', 'ind'),
              ('ik', 'ipk'), ('is', 'isl / ice*'), ('it', 'ita'), ('jv', 'jav'), ('ja', 'jpn'), ('kl', 'kal'), ('kn', 'kan'), ('ks', 'kas'), ('ka', 'kat / geo*'), ('kr', 'kau'), ('kk', 'kaz'), ('km', 'khm'), ('ki', 'kik'), ('rw', 'kin'), ('ky', 'kir'), ('kv', 'kom'), ('kg', 'kon'), ('ko', 'kor'),
              ('kj', 'kua'), ('ku', 'kur'), ('lo', 'lao'), ('la', 'lat'), ('lv', 'lav'), ('li', 'lim'), ('ln', 'lin'), ('lt', 'lit'), ('lb', 'ltz'), ('lu', 'lub'), ('lg', 'lug'), ('mh', 'mah'), ('ml', 'mal'), ('mr', 'mar'), ('mk', 'mkd / mac*'), ('mg', 'mlg'), ('mt', 'mlt'), ('mn', 'mon'),
              ('mi', 'mri / mao*'), ('ms', 'msa / may*'), ('my', 'mya / bur*'), ('na', 'nau'), ('nv', 'nav'), ('nr', 'nbl'), ('nd', 'nde'), ('ng', 'ndo'), ('ne', 'nep'), ('nl', 'nld / dut*'), ('nn', 'nno'), ('nb', 'nob'), ('no', 'nor* / nob / nno'), ('ny', 'nya'), ('oc', 'oci'), ('oj', 'oji'), ('or', 'ori'),
              ('om', 'orm'), ('os', 'oss'), ('pa', 'pan'), ('pi', 'pli'), ('pl', 'pol'), ('pt', 'por'), ('ps', 'pus'), ('qu', 'que'), ('rm', 'roh'), ('ro', 'ron / rum*'), ('rn', 'run'), ('ru', 'rus'), ('sg', 'sag'), ('sa', 'san'), ('si', 'sin'), ('sk', 'slk / slo*'), ('sl', 'slv'), ('se', 'sme'),
              ('sm', 'smo'), ('sn', 'sna'), ('sd', 'snd'), ('so', 'som'), ('st', 'sot'), ('es', 'spa'), ('sq', 'sqi / alb*'), ('sc', 'srd'), ('sr', 'srp'), ('ss', 'ssw'), ('su', 'sun'), ('sw', 'swa'), ('sv', 'swe'), ('ty', 'tah'), ('ta', 'tam'), ('tt', 'tat'), ('te', 'tel'), ('tg', 'tgk'),
              ('tl', 'tgl'), ('th', 'tha'), ('ti', 'tir'), ('to', 'ton'), ('tn', 'tsn'), ('ts', 'tso'), ('tk', 'tuk'), ('tr', 'tur'), ('tw', 'twi'), ('ug', 'uig'), ('uk', 'ukr'), ('ur', 'urd'), ('uz', 'uzb'), ('ve', 'ven'), ('vi', 'vie'), ('vo', 'vol'), ('wa', 'wln'), ('wo', 'wol'), ('xh', 'xho'),
              ('yi', 'yid'), ('yo', 'yor'), ('za', 'zha'), ('zh', 'zho / chi*'), ('zu', 'zul')]

class Settings(PluginSettings):
    settings = {
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

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

    # Get file suffix
    mkv = '.mkv'
    mp4 = '.mp4'
    sfx = os.path.splitext(abspath)[1]
    data['add_file_to_pending_tasks'] = False
    logger.debug("suffix: '{}'".format(sfx))
    if sfx == mkv or sfx == mp4:
        basefile = os.path.splitext(abspath)[0]
        logger.debug("basefile: '{}'".format(basefile))
        logger.debug("glob length: '{}'".format(len(glob.glob(glob.escape(basefile) + '*.*[a-z].srt'))))
        for j in range(len(glob.glob(glob.escape(basefile) + '*.*[a-z].srt'))):
            lang_srt = [li for li in difflib.ndiff(basefile, glob.glob(glob.escape(basefile) + '*.*[a-z].srt')[j]) if li[0] != ' ']
            lang = ''.join([i.replace('+ ','') for i in lang_srt]).replace('.srt','').replace('.','')
            logger.info ("Language code '{}' subtitle file found, adding file to task queue".format(lang))
            data['add_file_to_pending_tasks'] = True
        return data

def lang_split(lang):
    l = lang.split('/')
    l = [i.strip() for i in l]
    if len(l) > 1:
        l = [i for i in l if '*' in i]
    l = [l2.replace('*','') for l2 in l]
    return l[0]

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

    # Get the path to the input and output files
    abspath = data.get('file_in')
    outfile = data.get('file_out')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

    # get all streams
    streams=probe.get_probe()["streams"]

    # Get file suffix
    mkv = '.mkv'
    mp4 = '.mp4'
    encoder = 'copy'
    sfx = os.path.splitext(abspath)[1]
    if sfx == mp4: encoder = 'mov_text'

    # Get any existing subtitles
    existing_subtitle_streams_list = [i for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle"]
    existing_subtitle_streams_list_len = len(existing_subtitle_streams_list)

    # test suffix for video file
    if sfx == mkv or sfx == mp4:
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath)]
        ffmpeg_subtitle_args = []
        basefile = os.path.splitext(abspath)[0]

        # get all subtitle files in folder where original video file is, get 3 letter language code, build ffmpeg subtitle args for new streams
        for j in range(len(glob.glob(glob.escape(basefile) + '*.*[a-z].srt'))):
            ffmpeg_args += ['-i', str(glob.glob(glob.escape(basefile) + '*.*[a-z].srt')[j])]
            lang_srt = [li for li in difflib.ndiff(basefile, glob.glob(glob.escape(basefile) + '*.*[a-z].srt')[j]) if li[0] != ' ']
            lang = ''.join([i.replace('+ ','') for i in lang_srt]).replace('.srt','').replace('.','')
            if len(lang) == 2:
                try:
                    lang3 = [lang_codes[i][1] for i in range(len(lang_codes)) if lang == lang_codes[i][0]][0]
                    lang3 = lang_split(lang3)
                except (KeyError, IndexError):
                    logger.error("error translating language code of subtitle stream - aborting. language code: '{}'".format(lang))
                    return data
            elif len(lang) == 3:
                try:
                    lang3 = [lang_codes[i][1] for i in range(len(lang_codes)) if lang in lang_codes[i][1]][0]
                    lang3 = lang_split(lang3)
                except (KeyError, IndexError):
                    logger.error("error - 3 letter language code provided not found - aborting. language code: '{}'".format(lang))
                    return data
            else:
                logger.error("error - improper langauge code supplied - aborting. language code: '{}'".format(lang))
                return data
            ffmpeg_subtitle_args += ['-map', '{}:s:0'.format(j+1), '-c:s:{}'.format(j+existing_subtitle_streams_list_len), str(encoder), '-metadata:s:s:{}'.format(j+existing_subtitle_streams_list_len), 'language={}'.format(lang3)]

        # add in any existing subtitle streams
        for i in range(existing_subtitle_streams_list_len-1, -1, -1):
            ffmpeg_subtitle_args = ['-map', '0:s:{}'.format(i), '-c:s:{}'.format(i), 'copy'] + ffmpeg_subtitle_args

        # build rest of ffmpeg_args around ffmpeg_subtitle_args
        ffmpeg_args += ['-max_muxing_queue_size', '9999', '-strict', '-2', '-map', '0:v', '-c:v', 'copy', '-map', '0:a', '-c:a', 'copy'] + ffmpeg_subtitle_args + ['-map', '0:t?', '-c:t', 'copy', '-map', '0:d?', '-c:d', 'copy']
        if sfx == mp4:
            ffmpeg_args += ['-dn', '-map_metadata:c', '-1', '-y', str(outfile)]
        else:
            ffmpeg_args += ['-y', str(outfile)]

        if ffmpeg_subtitle_args:
            # external subtitle file(s) were found for video file
            logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

            # Apply ffmpeg args to command
            data['exec_command'] = ['ffmpeg']
            data['exec_command'] += ffmpeg_args

            # Set the parser
            parser = Parser(logger)
            parser.set_probe(probe)
            data['command_progress_parser'] = parser.parse_progress

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

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    status = data.get('task_processing_success')
    logger.debug("status: '{}'".format(status))

    if status:
        abspath = data.get('source_data').get('abspath')
        basefile = os.path.splitext(abspath)[0]
        srt_files = glob.glob(glob.escape(basefile) + '*.*[a-z].srt')
        logger.debug("basefile in post: '{}'".format(basefile))
        logger.debug("srt files: '{}'".format(srt_files))
        for j in range(len(srt_files)):
            srt_file = srt_files[j]
            os.remove(srt_file)
            logger.info("srt file '{}' has been added to video file of the same basename; the srt file has been deleted.".format(srt_file))

    return data
