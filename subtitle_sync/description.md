
##### Description
This plugin will sync subtitles to the video.

##### Reference
See [ffsubsync github](https://github.com/smacke/ffsubsync) and/or 
[ffsubsync documentation](https://ffsubsync.readthedocs.io/en/latest/)

##### Configuration
- Enter a comma delimited list of subtitle languages to sync.  To sync a subtitle file, there must be BOTH a subtitle language file and a corresponding
  audio stream in the same language.  If you wish to sync all associated subtitle files wiht a corresponding video, enter *.  Two letter or three letter
  language codes can be used - the plugin will automatically match the given code to the subtitle file.
- prefer_mc_or_st - in the case where a given language exists in both multichannel and stereo format, pick which stream type you wish to sync the subtitle.

:::note
In the case where there are multiple language streams meeting the matching criteria of language and multichannel/stereo preference, the plugin will pick
the audio stream with the highest bit rate.
:::

:::important
This plugin will only work for text subtitles like srt.  The format for the filename should be video_file_name_sans_extension.lang_code.srt for an srt file.
The lang_code can be either 2 letters or 3 letters, e.g., fr or fre or fra for French.
:::
