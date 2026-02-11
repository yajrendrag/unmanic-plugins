
This plugin will rename your file by either appending selected fields from ffprobe values to the name of the file just before the file's suffix, OR
it looks for video codec, audio codec and resolution data already in the filename as parsed by PTN and replaces those substrings with the transcoded
file's new ffprobe values.

To select wth appropriate action, the first option governs which of the above scenarios are implemented:
To implement the first scenario, uncheck this option:
Check this option if you want replace existing fields names with new values from ffprobe of transcoded file; uncheck if your wish to append new fields to file name from ffprobe metadata

Then, continue to configure the plugin by choosing the ffprobe fields to add.  By default, the plugin will add the video codec_name.  You can choose to add
additional fields:

-video_resolution
-audio codec of the designated audio stream
-audio channel format of the designated audio stream
-audio language of the designated audio stream

The designated audio stream will be selected automatically based on the following criteria:

-first audio stream in the file
-the first audio stream marked as default audio stream

If audio language is selected and the designated audio stream does not have a language tag, or the langauge tag is "und" the language tag will be omitted.

To implement the second scenario, check this option:
Check this option if you want replace existing fields names with new values from ffprobe of transcoded file; uncheck if your wish to append new fields to file name from ffprobe metadata

If other components are desired, consider using filebot - see instructions at https://docs.unmanic.app/docs/guides/filebot_post_processor
