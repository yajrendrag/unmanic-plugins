
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

- This plugin converts all 6 channel (or greater) audio streams matching an audio codec from your configured list of audio codecs to either aac (native or libfdk_aac) or ac3
- The resulting audio streams are still 6 channel streams (8 channel streams need to be converted to 6 channel as ffmpeg cannot encode more than 6 channels to aac or ac3)
- The original stream(s) is(are) that is(are) converted are no longer present at the conclusion of this plugin's operation
---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - High Quality Audio Encoding](https://trac.ffmpeg.org/wiki/Encode/HighQualityAudio)
--- 

##### Config description:

- bit_rate - set the aggregate bit rate for all audio streams.  The default setting is 640k
- stream_title - enter a custom stream title if desired, or if left empty, the default is to use a string equal to the encoder name plus "5.1 Surround"
- encoder - select the encoder to use - you can pick from aac (ffmpeg native aac), ac3, or libfdk_aac.
- mc_codecs - a comma delimited list of multichannel audio codecs to be converted by this plugin, e.g., dts,eac3
