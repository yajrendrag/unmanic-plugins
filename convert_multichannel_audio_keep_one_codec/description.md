
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

- This plugin converts all 6 channel (or greater) multichannel audio to ac3 or aac
- The resulting audio streams are still 6 channel streams
- If aac is selected libfdk_aac is used for the encoder
- The original stream(s) is(are) no longer present at the conclusion of this plugin's operation
- optionally keeps one of the original codec streams as is
---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - High Quality Audio Encoding](https://trac.ffmpeg.org/wiki/Encode/HighQualityAudio)
--- 

##### Config description:

bit_rate - set the aggregate bit rate for all audio streams.  The default setting is 640k
