#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               Josh.5 <jsunnex@gmail.com>, senorsmartypants@gmail.com, yajrendrag@gmail.com
    Date:                     30 Sep 2021, (03:45 PM)

    Copyright:
        Copyright (C) 2021 Josh Sunnex

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
from configparser import NoSectionError, NoOptionError
from langcodes.tag_parser import LanguageTagError
from langcodes import *

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

from keep_stream_by_language.lib.ffmpeg import StreamMapper, Probe, Parser
from keep_stream_by_language.lib.tmdb_original import get_original_language

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.keep_stream_by_language")


class Settings(PluginSettings):
    settings = {
        "audio_languages":       '',
        "subtitle_languages":    '',
        "keep_undefined":        True,
        "keep_commentary":       False,
        "fail_safe":             True,
        "reorder_kept":          True,
        "prefer_2_or_mc":        "2",
        "keep_original_audio":   False,
        "tmdb_api_key":    "",
        "tmdb_api_read_access_token":    "",
        "tmdb_language_overrides":    'cn=zh',
    }


    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "audio_languages": {
                "label": "Enter comma delimited list of audio languages to keep",
            },
            "subtitle_languages": {
                "label": "Enter comma delimited list of subtitle languages to keep",
            },
            "keep_undefined":	{
                "label": "check to keep streams with no language tags or streams with undefined/unknown language tags",
            },
            "keep_commentary":   {
                "label": "uncheck to discard commentary audio streams regardless of any language tags",
            },
            "fail_safe":   {
                "label": "check to include fail safe check to prevent unintentional deletion of all audio streams",
            },
            "reorder_kept":   {
                "description": "if checked, this will reorder the kept audio streams by making the first stream(s) in the file, those streams that match the first audio language listed above; audio stream 0 will also have default disposition set",
                "label": "reorder kept audio languages",
            },
            "prefer_2_or_mc": self.__set_audio_default_prefs_form_settings(),
            "keep_original_audio":   {
                "description": "if checked, this will perform a lookup in tmdb (the movie database) and also add the original audio language tag to the list of audio languages to keep",
                "label": "Keep Original Audio Language",
            },
            "tmdb_api_key": self.__set_tmdb_api_key_form_settings(),
            "tmdb_api_read_access_token": self.__set_tmdb_api_read_access_token_form_settings(),
            "tmdb_language_overrides": self.__set_tmdb_language_overrides_form_settings(),
        }

    def __set_audio_default_prefs_form_settings(self):
        values = {
            "description": "If reordering kept audio streams, specify if you prefer 2 channel or multichannel to be the default audio when the file has more than one stream that matches the language tag listed first in the list of audio languages.",
            "label":      "Enter Choice",
            "input_type": "select",
            "select_options": [
                {
                    "value": "2",
                    "label": "Set 2 Channel as default",
                },
                {
                    "value": "mc",
                    "label": "Set Multichannel as default",
                },
            ],
        }
        if not self.get_setting('reorder_kept'):
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_read_access_token_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api read access token",
            "input_type": "textarea",
        }
        if not self.get_setting('keep_original_audio'):
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_key_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api key",
            "input_type": "textarea",
        }
        if not self.get_setting('keep_original_audio'):
            values["display"] = 'hidden'
        return values

    def __set_tmdb_language_overrides_form_settings(self):
        values = {
            "label":      "TMDB original-language code substitutions",
            "description": "Some TMDB original-language codes are not valid ISO language tags and will not match "
                           "any audio stream (they get dropped, and the original stream is not kept). Enter "
                           "comma-separated substitutions as code=replacement. TMDB uses 'cn' for Cantonese: map "
                           "it to 'zh' (default) to match streams tagged chi/zho/zh, or to 'yue' to match only "
                           "streams tagged yue. Use 'code=' with an empty replacement to drop a code entirely "
                           "(e.g. 'xx='). Whenever a substitution fires it is logged at INFO level.",
            "input_type": "textarea",
        }
        if not self.get_setting('keep_original_audio'):
            values["display"] = 'hidden'
        return values

class PluginStreamMapper(StreamMapper):
    def __init__(self):
        super(PluginStreamMapper, self).__init__(logger, ['audio','subtitle'])
        self.settings = None
        # Per-file audio language list (configured languages, optionally augmented with the
        # file's original language). Set per file test by the runner; never a module global.
        self.alcl = ''

    def set_settings(self, settings):
        self.settings = settings

    def null_streams(self, streams):
        logger.debug(f"alcl: {self.alcl}")
        alcl, audio_streams_list = streams_list(self.alcl, streams, 'audio')
        # slcl, subtitle_streams_list = streams_list(self.settings.get_setting('subtitle_languages'), streams, 'subtitle')
        # This change in the line below results in the fail-safe to only apply to audio streams
        alcl = [standardize_tag(l) if l != '*' else '*' for l in alcl]
        audio_streams_list = [standardize_tag(l) for l in audio_streams_list]
        if (any(l in audio_streams_list for l in alcl) or alcl == ['*'] or audio_streams_list == []): # and (any(l in subtitle_streams_list for l in slcl) or slcl == ['*'] or subtitle_streams_list == []):
            return True
        logger.info("Audio streams list of languages does not contain a language matching any streams in the file - all audio streams would be removed if processed, fail-safe should prevent this from ocurring.\n alcl: '{}', audio streams in file: '{}'".format(alcl, audio_streams_list))
        return False

    def same_streams_or_no_work(self, streams, keep_undefined):
        alcl, audio_streams_list = streams_list(self.alcl, streams, 'audio')
        slcl, subtitle_streams_list = streams_list(self.settings.get_setting('subtitle_languages'), streams, 'subtitle')
#        if not audio_streams_list or not subtitle_streams_list:
#            return False
        untagged_streams = [i for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] in ["audio", "subtitle"] and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]

        # if subtitle or audio _streams_list is empty the "all" statements will not test properly so the if statements work around this
        # and then we set the audio/subtitle_in a/slcl to True so no_work_to_do is properly determined.

        alcl = [standardize_tag(l) if l != '*' else '*' for l in alcl]
        audio_streams_list = [standardize_tag(l) for l in audio_streams_list]
        slcl = [standardize_tag(l) if l != '*' else '*' for l in slcl]
        subtitle_streams_list = [standardize_tag(l) for l in subtitle_streams_list]
        if subtitle_streams_list and slcl != ['*']:
            subs_in_slcl = all(l in slcl for l in subtitle_streams_list)
        else:
            subs_in_slcl = True
        if audio_streams_list and alcl != ['*']:
            audio_in_alcl = all(l in alcl for l in audio_streams_list)
        else:
            audio_in_alcl = True
        no_work_to_do = (subs_in_slcl and audio_in_alcl and (keep_undefined == True or (keep_undefined == False and untagged_streams == [])))
        logger.debug("audio config list: '{}', audio streams in file: '{}'".format(alcl, audio_streams_list))
        logger.debug("subtitle config list: '{}', subtitle streams in file: '{}'".format(slcl, subtitle_streams_list))
        logger.debug("untagged streams: '{}'".format(untagged_streams))
        logger.debug("subs in slcl: '{}'; audio in alcl: '{}'".format(subs_in_slcl, audio_in_alcl))
        logger.debug("no work to do: '{}'".format(no_work_to_do))
        if ((alcl == audio_streams_list or alcl == ['*'])  and (slcl == subtitle_streams_list or slcl == ['*'])) or no_work_to_do:
            return True
        else:
            return False

    def test_tags_for_search_string(self, codec_type, stream_tags, stream_id):
        keep_undefined  = self.settings.get_setting('keep_undefined')
        # TODO: Check if we need to add 'title' tags
        if stream_tags and True in list(k.lower() in ['language'] for k in stream_tags):
            # check codec and get appropriate language list
            if codec_type == 'audio':
                language_list = self.settings.get_setting('audio_languages')
            else:
                language_list = self.settings.get_setting('subtitle_languages')
            languages = list(filter(None, language_list.split(',')))
            languages = [languages[i].strip() for i in range(len(languages))]
            if '*' not in languages and languages:
                try:
                    languages = [languages[i] if Language.get(languages[i]).is_valid() else "" for i in range(len(languages))]
                except LanguageTagError:
                    raise

            for language in languages:
                language = language.strip().lower()
                try:
                    stream_tag_language = stream_tags.get('language', '') if Language.get(stream_tags.get('language', '')).is_valid() else ""
                except LanguageTagError:
                    raise

                if language == '*':
                    return True
                elif language and (standardize_tag(language) in [standardize_tag(stream_tag_language)]):
                    return True

        elif keep_undefined:
            logger.warning(
                "Stream '{}' in file '{}' has no language tag, but keep_undefined is checked. add to queue".format(stream_id, self.input_file))
            return True

        else:
            logger.warning(
                "Stream '{}' in file '{}' has no language tag. Ignoring".format(stream_id, self.input_file))
        return False

    def test_stream_needs_processing(self, stream_info: dict):
        """Only add streams that have language task that match our list"""
        return self.test_tags_for_search_string(stream_info.get('codec_type', '').lower(), stream_info.get('tags'), stream_info.get('index'))

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        """Remove this stream"""
        return {
            'stream_mapping':  [],
            'stream_encoding': [],
        }

def is_valid_lang(code):
    # True only for codes langcodes both parses and considers valid. Anything else
    # (empty, malformed, or syntactically-fine-but-unassigned like TMDB's 'cn') is invalid.
    if not code:
        return False
    try:
        return Language.get(code).is_valid()
    except LanguageTagError:
        return False

def streams_list(languages, streams, stream_type):
    language_config_list = languages
    lcl = [c.strip() for c in language_config_list.split(',') if c.strip()]
    lcl.sort()
    if '*' not in lcl and lcl:
        # Drop invalid codes rather than blanking them to '' — a '' element crashes the
        # standardize_tag() pass in null_streams/same_streams_or_no_work. An invalid code
        # here can't match a stream anyway, so dropping it is the correct no-op.
        invalid = [c for c in lcl if not is_valid_lang(c)]
        if invalid:
            logger.warning("ignoring invalid {} language code(s) in config: {}".format(stream_type, invalid))
        lcl = [c for c in lcl if is_valid_lang(c)]

    try:
        streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == stream_type and "tags" in streams[i] and "language" in streams[i]["tags"] and
                        ("title" in streams[i]["tags"] and "commentary" not in streams[i]["tags"]["title"].lower() or "title" not in streams[i]["tags"])]
        streams_list.sort()
    except KeyError:
        streams_list = []
        logger.info("no '{}' tags in file".format(stream_type))
    if streams_list:
        # Same reasoning on the stream side: a stream tagged with an invalid code (e.g. a
        # bad muxer tag) would otherwise become '' and crash the standardize_tag() pass.
        invalid = [c for c in streams_list if not is_valid_lang(c)]
        if invalid:
            logger.warning("ignoring {} stream(s) with invalid language tag(s): {}".format(stream_type, invalid))
        streams_list = [c for c in streams_list if is_valid_lang(c)]

    return lcl,streams_list

def kept_streams(settings):
    # Fingerprint only (file_streams_already_kept checks presence, not content), so the
    # configured audio_languages is sufficient here — no need for the per-file augmented list.
    al = settings.get_setting('audio_languages') or ''
    sl = settings.get_setting('subtitle_languages')
    if not sl:
        sl = settings.settings.get('subtitle_languages')
    ku = settings.get_setting('keep_undefined')
    if not ku:
        ku = settings.settings.get('keep_undefined')
    kc = settings.get_setting('keep_commentary')
    if not kc:
        kc = settings.settings.get('keep_commentary')
    fs = settings.get_setting('fail_safe')
    if not fs:
        fs = settings.settings.get('fail_safe')

    return 'kept_streams=audio_langauges={}:subtitle_languages={}:keep_undefined={}:keep_commentary={}:fail_safe={}'.format(al, sl, ku, kc, fs)

def file_streams_already_kept(settings, path, file_metadata=None):
    # New mechanism: Unmanic's per-file task metadata store (injected as file_metadata).
    # In a library scan get() fingerprints `path` and returns this plugin's committed
    # metadata; during a task it returns the task's merged metadata.
    if file_metadata is not None:
        try:
            metadata = file_metadata.get()
            if metadata.get('streams_kept'):
                logger.debug("File '{}' streams previously kept (task metadata): {}".format(path, metadata.get('streams_kept')))
                return True
        except Exception as e:
            logger.debug("Unable to read UnmanicFileMetadata for '{}': {}".format(path, e))

    # Legacy mechanism: the .unmanic directory-info file. Always consulted when the store has
    # no marker, so files marked by older plugin versions are still recognized as processed.
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))

    try:
        streams_already_kept = directory_info.get('keep_streams_by_language', os.path.basename(path))
    except NoSectionError as e:
        streams_already_kept = ''
    except NoOptionError as e:
        streams_already_kept = ''
    except Exception as e:
        logger.debug("Unknown exception {}.".format(e))
        streams_already_kept = ''

    if streams_already_kept:
        logger.debug("File's streams were previously kept with {} (legacy .unmanic).".format(streams_already_kept))
        return True

    # Default to...
    return False

def parse_tmdb_language_overrides(raw):
    # "cn=zh, xx=" -> {'cn': 'zh', 'xx': None}. An empty replacement means "drop this code".
    overrides = {}
    for pair in (raw or '').split(','):
        pair = pair.strip()
        if not pair:
            continue
        key, _, value = pair.partition('=')
        key = key.strip().lower()
        value = value.strip().lower()
        if key:
            overrides[key] = value or None
    return overrides

def build_audio_language_list(path, settings):
    """Return the configured audio_languages, optionally augmented with the file's original
    language from TMDB. Pure function: returns a comma-delimited string, mutates no globals,
    so concurrent file tests can't clobber each other's language list."""
    langs = settings.get_setting('audio_languages') or ''
    filename = os.path.basename(path)
    tmdb_api_key = settings.get_setting('tmdb_api_key')
    # NOTE: was previously get_setting('tmdb_read_access_token') — a key that does not exist,
    # so the read access token was always None. Corrected to the real setting key.
    tmdb_read_access_token = settings.get_setting('tmdb_api_read_access_token')

    original_language = get_original_language(filename, tmdb_api_key, tmdb_read_access_token)
    logger.debug(f"original language {original_language}")
    if not original_language:
        logger.info(f"no original language returned for {filename}; audio language list is configured languages only")
        return langs

    raw_code = str(original_language[0]).strip().lower()
    if not raw_code:
        return langs

    overrides = parse_tmdb_language_overrides(settings.get_setting('tmdb_language_overrides'))
    mapped = overrides.get(raw_code, raw_code)
    if mapped is None:
        logger.info(f"TMDB original language '{raw_code}' is configured to be dropped; not augmenting")
        return langs
    if mapped != raw_code:
        logger.info(f"TMDB original language '{raw_code}' -> '{mapped}' (via tmdb_language_overrides)")

    try:
        new = standardize_tag(mapped)
    except LanguageTagError:
        new = None
    if not is_valid_lang(new):
        logger.warning(
            f"TMDB original language '{raw_code}' is not a valid language tag and will not match any "
            f"stream; not augmenting. Add a substitution such as '{raw_code}=zh' or '{raw_code}=yue' "
            f"in the tmdb_language_overrides setting.")
        return langs

    cl = [standardize_tag(p.strip()) for p in langs.split(',') if p.strip()]
    if new not in cl:
        cl.append(new)
    result = ','.join(cl)
    logger.debug(f"audio language list: {result}")
    return result

def on_library_management_file_test(data, task_data_store=None, file_metadata=None):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.

    :param data:
    :return:

    """
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # If the config is empty (not yet configured) ignore everything
    if not settings.get_setting('audio_languages') and not settings.get_setting('subtitle_languages'):
        logger.debug("Plugin has not yet been configured with a list languages to remove allow. Blocking everything.")
        return False

    # Get the path to the file
    abspath = data.get('path')

    # Build the audio language list, augmenting with the file's original language only when enabled.
    keep_original_lang = settings.get_setting('keep_original_audio')
    if keep_original_lang:
        alcl_value = build_audio_language_list(abspath, settings)
    else:
        alcl_value = settings.get_setting('audio_languages') or ''

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

    # get all streams
    probe_streams=probe.get_probe()["streams"]

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_settings(settings)
    mapper.alcl = alcl_value
    mapper.set_probe(probe)

    # Set the input file
    mapper.set_input_file(abspath)

    # Get fail-safe setting
    fail_safe = settings.get_setting('fail_safe')
    keep_undefined = settings.get_setting('keep_undefined')

    if not file_streams_already_kept(settings, abspath, file_metadata=file_metadata):
        logger.debug("File '{}' has not previously had streams kept by keep_streams_by_language plugin".format(abspath))
        if fail_safe:
            if not mapper.null_streams(probe_streams):
                logger.debug("File '{}' does not contain streams matching any of the configured languages - if * was configured or the file has no streams of a given type, this check will not prevent the plugin from running for that stream type.".format(abspath))
                return data
        if mapper.same_streams_or_no_work(probe_streams, keep_undefined):
            logger.debug("File '{}' only has same streams as keep configuration specifies OR otherwise does not require any work to keep ony specified streams - so, does not contain streams that require processing.".format(abspath))
        elif mapper.streams_need_processing():
            # Mark this file to be added to the pending tasks
            data['add_file_to_pending_tasks'] = True
            logger.debug("File '{}' should be added to task list. Probe found streams require processing.".format(abspath))
        else:
            logger.debug("File '{}' does not contain streams that require processing.".format(abspath))

    del mapper

    return data

def keep_languages(mapper, ct, language_list, streams, keep_undefined, keep_commentary):
    codec_type = ct[0].lower()
    languages = list(filter(None, language_list.split(',')))
    languages = [languages[i].lower().strip() for i in range(0,len(languages))]
    if '*' not in languages and languages:
        try:
            languages = [languages[i] if Language.get(languages[i]).is_valid() else "" for i in range(len(languages))]
        except LanguageTagError as e:
            e.args += ("config list: " + str(languages),)
            raise

    streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == ct and "tags" in streams[i] and "language" in streams[i]["tags"] and
                    (codec_type == 's' or keep_commentary == True or (keep_commentary == False and ("codec_type" in streams[i] and streams[i]["codec_type"] == ct and "tags" in streams[i] and ("title" in streams[i]["tags"] and
                     "commentary" not in streams[i]["tags"]["title"].lower() or "title" not in streams[i]["tags"]))) or languages == ['*'])]

    languages = [standardize_tag(l) if l != '*' else '*' for l in languages]

    try:
        streams_list = [streams_list[i] if Language.get(streams_list[i]).is_valid() else "" for i in range(len(streams_list))]
    except LanguageTagError as e:
        e.args += ("invalid stream language: " + str(streams_list[i]),)
        raise

    streams_list = [standardize_tag(l) if l != '*' else '*' for l in streams_list]
    if streams_list:
        for i, language in enumerate(streams_list):
            lang = language.lower().strip()
            if lang and not (keep_undefined and lang == "und") and (lang in languages or languages == ['*']):
                logger.debug("keeping language '{}' from '{}' stream '{}.".format(lang, ct, i))
                mapadder(mapper, i, codec_type)

def keep_undefined(mapper, streams, keep_commentary):
    if keep_commentary:
        audio_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio" and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]
    else:
        audio_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio" and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"]) or
                              ("tags" in streams[i] and "title" in streams[i]["tags"] and "commentary" not in streams[i]["tags"]["title"].lower()))]
    subtitle_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle" and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]
    stream_iterator(mapper, subtitle_streams_list, streams, 's')
    stream_iterator(mapper, audio_streams_list, streams, 'a')

def stream_iterator(mapper, stream_list, streams, codec):
    for i in range(0, len(stream_list)):
        try:
            lang = streams[stream_list[i]]["tags"]["language"].lower().strip()
        except KeyError:
            logger.debug("keeping untagged stream '{}.".format(i))
            mapadder(mapper, i, codec)
        else:
            if lang == 'und':
                logger.debug("keeping stream '{}' marked as undefined.".format(i))
                mapadder(mapper, i, codec)

def mapadder(mapper, stream, codec):
    mapper.stream_mapping += ['-map', '0:{}:{}'.format(codec, stream)]
    #mapper.stream_encoding += ['-c:{}:{}'.format(codec, stream), 'copy']

def reorder_audio_streams(stream_map, mapper, prefer_2_or_mc, ffmpeg_args, probe_streams, def_lang):
    as_list=[]
    for stream in range(len(stream_map)):
        if stream_map[stream] == '-map' or stream_map[stream] == '0:v':
            continue
        elif stream_map[stream].split(':')[1] == 'a':
            as_list.append(stream_map[stream].split(':')[2])
    all_astreams=[probe_streams[i]['index'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio']
    abs_streams = [all_astreams[i] for i, a in enumerate(all_astreams) if str(i) in as_list]
    new_order = [i for i in abs_streams if 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] == def_lang] + \
                [i for i in abs_streams if 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] != def_lang]

    idx_map = [i for i, v in enumerate(abs_streams) if 'tags' in probe_streams[v] and 'language' in probe_streams[v]['tags'] and probe_streams[v]['tags']['language'] == def_lang] + \
              [i for i, v in enumerate(abs_streams) if 'tags' in probe_streams[v] and 'language' in probe_streams[v]['tags'] and probe_streams[v]['tags']['language'] != def_lang]
    new_map = [as_list[i] for i in idx_map]
    langs = [probe_streams[i]['tags']['language'] for i in new_order]
    matched_langs = [l for l in langs if l == def_lang]
    if len(matched_langs) > 1:
        channels = probe_streams[new_order[0]]['channels']
        if (prefer_2_or_mc == '2' and channels != 2) or (prefer_2_or_mc == 'mc' and channels == 2):
            for i in range(1, len(matched_langs)):
                channels = probe_streams[new_order[i]]['channels']
                if (prefer_2_or_mc == '2' and channels == 2) or (prefer_2_or_mc == 'mc' and channels > 2):
                    # switch i & 0
                    original_first_abs_stream = new_order[0]
                    original_first_new_map = new_map[0]
                    new_order[0] = new_order[i]
                    new_map[0] = new_map[i]
                    new_order[i] = original_first_abs_stream
                    new_map[i] = original_first_new_map
                    break
    mapper.stream_mapping = ['-map', '0:v']
    for i,astream in enumerate(new_map):
        mapper.stream_mapping += ['-map', f"0:a:{astream}"]
        if i == 0:
            mapper.stream_mapping += ["-disposition:a:"+str(0), "default"]
    logger.debug(f"mapper.stream_mapping: {mapper.stream_mapping}")
    kwargs = {"-disposition:a": '-default'}
    mapper.set_ffmpeg_advanced_options(**kwargs)
    logger.debug(f"ffmpeg_args: {ffmpeg_args}")

def on_worker_process(data, task_data_store=None, file_metadata=None):
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

    # Get the path to the file
    abspath = data.get('file_in')

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Build the audio language list, augmenting with the file's original language only when enabled.
    keep_original_lang = settings.get_setting('keep_original_audio')
    if keep_original_lang:
        path = data.get('original_file_path')
        alcl_value = build_audio_language_list(path, settings)
    else:
        alcl_value = settings.get_setting('audio_languages') or ''

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data
    else:
        probe_streams = probe.get_probe()["streams"]

    keep_undefined_lang_tags = settings.get_setting('keep_undefined')
    keep_commentary = settings.get_setting('keep_commentary')
    reorder_kept = settings.get_setting('reorder_kept')
    if reorder_kept:
        prefer_2_or_mc = settings.get_setting('prefer_2_or_mc')

    if not file_streams_already_kept(settings, data.get('original_file_path'), file_metadata=file_metadata):
        # Get stream mapper
        mapper = PluginStreamMapper()
        mapper.set_settings(settings)
        mapper.alcl = alcl_value
        mapper.set_probe(probe)

        # Set the input file
        mapper.set_input_file(abspath)

        # Get fail-safe setting
        fail_safe = settings.get_setting('fail_safe')

        # Get results of streams needing processing
        streams_need_processing = mapper.streams_need_processing()

        # Test for null intersection of configured languages and actual languages
        keep_all_audio = False
        if fail_safe:
            if not mapper.null_streams(probe_streams):
                logger.info("File '{}' does not contain audio streams matching any of the configured languages - keeping all audio streams.".format(abspath))
                keep_all_audio = True
        if mapper.same_streams_or_no_work(probe_streams, keep_undefined_lang_tags):
            logger.debug("File '{}' only has same streams as keep configuration specifies OR otherwise does not require any work to keep ony specified streams - so, does not contain streams that require processing.".format(abspath))
        elif streams_need_processing or (keep_all_audio and not keep_commentary):
            logger.debug("File '{}' Proceeding with worker - probe found streams require processing.".format(abspath))
            # Set the output file
            mapper.set_output_file(data.get('file_out'))

            # clear stream mappings, copy all video
            mapper.stream_mapping = ['-map', '0:v']
            mapper.stream_encoding = []

            # keep specific language streams if present
            if not keep_all_audio:
                keep_languages(mapper, 'audio', alcl_value, probe_streams, keep_undefined_lang_tags, keep_commentary)
                def_lang = alcl_value
                if reorder_kept and def_lang != '*':
                    lcl = list(def_lang.split(','))
                    lcl = [lcl[i].strip() for i in range(0,len(lcl))]
                    if lcl: def_lang = lcl[0]
                    stream_map = mapper.stream_mapping
                    ffmpeg_args = mapper.get_ffmpeg_args()
                    reorder_audio_streams(stream_map, mapper, prefer_2_or_mc, ffmpeg_args, probe_streams, def_lang)
            else:
                # Only map non commentary streams if keep commentary is False
                if keep_commentary:
                    mapper.stream_mapping += ['-map', '0:a?']
                else:
                    astreams = [probe_streams[i]["index"] for i in range(len(probe_streams)) if probe_streams[i]["codec_type"] == 'audio']
                    audio_streams_to_map = [astreams[a] for a,i in enumerate(astreams) if "commentary" not in probe_streams[i]["tags"]["title"].lower()]
                    for i in range(len(audio_streams_to_map)):
                        mapper.stream_mapping += ['-map', f"0:a:{i}"]

            if settings.get_setting('subtitle_languages') != '*':
                keep_languages(mapper, 'subtitle', settings.get_setting('subtitle_languages'), probe_streams, keep_undefined_lang_tags, keep_commentary)

            # keep undefined language streams if present
            if keep_undefined_lang_tags:
                keep_undefined(mapper, probe_streams, keep_commentary)

            # Get generated ffmpeg args
            if settings.get_setting('subtitle_languages') == '*':
                mapper.stream_mapping += ['-map', '0:s?']
            mapper.stream_encoding += ['-c', 'copy']
            ffmpeg_args = mapper.get_ffmpeg_args()

            logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

            # Apply ffmpeg args to command
            data['exec_command'] = ['ffmpeg']
            data['exec_command'] += ffmpeg_args

            # Set the parser
            parser = Parser(logger)
            parser.set_probe(probe)
            data['command_progress_parser'] = parser.parse_progress
        else:
            logger.debug("Worker will not process file '{}'; it does not contain streams that require processing.".format(abspath))
    return data

def on_postprocessor_task_results(data, task_data_store=None, file_metadata=None):
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
    # We only care that the task completed successfully.
    # If a worker processing task was unsuccessful, dont mark the file streams as kept
    # TODO: Figure out a way to know if a file's streams were kept but another plugin was the
    #   cause of the task processing failure flag
    if not data.get('task_processing_success'):
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    marker = kept_streams(settings)

    # New mechanism: stage this plugin's marker in Unmanic's task metadata store. Destination
    # scope (the default) means the core commits it to every destination file's fingerprint
    # after this runner returns, so a future library scan of the processed file finds it via
    # file_metadata.get(). One set() call covers all destination files — no per-file loop.
    if file_metadata is not None:
        try:
            file_metadata.set({'streams_kept': marker})
            logger.debug("Keep streams by language marker written to task metadata store.")
            return data
        except Exception as e:
            logger.debug("Unable to write UnmanicFileMetadata: {}; falling back to directory info".format(e))

    # Fallback: legacy .unmanic directory-info file, one entry per destination file.
    # note that this should only happen for newly processed files on pre v0.4 unmanic and the existence of task data store
    for destination_file in data.get('destination_files'):
        directory_info = UnmanicDirectoryInfo(os.path.dirname(destination_file))
        directory_info.set('keep_streams_by_language', os.path.basename(destination_file), marker)
        directory_info.save()
        logger.debug("Keep streams by language marker written for '{}' into .unmanic file.".format(destination_file))
    return data
