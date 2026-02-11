---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin adds an external subtitle file into the video file of the same name, e.g, if a subtitle file named "video_file.xx.srt" exists in a folder and there is also a video file named "video_file.mp4" or a video file named
"video_file.mkv" then the plugin will add the contents of "video_file.xx.srt" as a subtitle stream with language tag of "xx" to "video_file.mp4" or "video_file.mp4".  It will add the srt subtitle stream as is to mkv files
and it will transcode the srt to mov_text format if it's an mp4 file.

---
### Config description:

As of version 0.1.0 there is now a single option to set the tag style.  Select whether you want the language tag of the subtitle stream to be 2 letters or 3 letters.  The default is to use 3 letters.

---
### Notes:

This plugin does not support linked instances UNLESS the linked instance has access to the media library using identical paths as the main (task sending) instance. 
