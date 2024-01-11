---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin strips all streams from the source video other than video and audio streams - all subtitles, attachements, data streams are removed.
Note that this is a very destructive plugin - all streams other than audio and video will be removed - it will also remove any chapters.
However, if there are multiple audio and/or multiple video streams, all of those streams will remain intact.
---
### Config description:

There is a single option to extract subtitles - which it will convert to srt (subrip) format.  this will probably not work with image subtitles.
The subtitle files will be extracted to the directory of the original file.
Each subtitle stream will be saved with the name of the file and extension of ".lang_code.file_suffix", so if the video file is named
video_file.mkv, and has eng and spa subtitles, the subtitle files will be name video_file.eng.srt and video_file.spa.srt.
If any subtitle stream does not have a language code, the language code in the name will be replaced by the absolute stream number, e.g.
if the 4th stream in the file is a subtitle with no language code it will be saved as video_file.3.srt (ffmpeg numbers streams starting at 0).
---
### Installation Notes
This plugin uses init.d folder to install plugin. After installing the plugin you will notice an error in the unmanic.log file about being
unable to locate ffsubsync.  This is normal given the installation method.  After installing the plugin, restart the unmanic container.  If however, your unmanic installation is pip installed on bare metal, then you can avoid this step by doing pip install ffsubsync before installing 
the plugin.
