
This plugin will rename your file by appending selected fields from ffprobe values to the name of the file just before the file's suffix.

Configure the plugin by choosing the ffprobe fields to add.  By default, the plugin will add the video codec_name.  You can choose to add
additional fields:

-video_resolution
-audio codec of the designated audio stream
-audio channel format of the designated audio stream
-audio language of the designated audio stream

The designated audio stream will be selected automatically based on the following criteria:

-first audio stream in the file
-the first audio stream marked as default audio stream

If audio language is selected and the designated audio stream does not have a language tag, or the langauge tag is "und" the language tag will be omitted.

If other components are desired, consider using filebot - see instructions at https://docs.unmanic.app/docs/guides/filebot_post_processor
