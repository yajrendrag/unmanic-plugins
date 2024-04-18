
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin is for use on Audio files - not video files.

It will transcode all audio streams in the file to the encoder specified in the plugin configuration.

If any stream has greater than 6 channels, it will be encoded to have only 6 channels - this is a current limitation of ffmpeg.

This Plugin will set the bit rate for each stream based on the channel rate specified and number of channels in the stream OR optionally it will use the bit rate of the original stream

As a rule of thumb, for audible transparency, use 64 kBit/s for each channel (so 128 kBit/s for stereo, 384 kBit/s for 5.1 surround sound). 

This Plugin will detect the number of channels in each stream and apply a bitrate in accordance with this rule.

---

##### Documentation:

For information on the available encoder settings:
- [High Quality Lossy Audio Encoding](https://trac.ffmpeg.org/wiki/Encode/HighQualityAudio)

--- 

### Config description:

#### <span style="color:blue">Select Encoder</span>

- Select the desired encoder: libmp3lame, libfdk_aac, flac, alac, libopus, vorbis.
- Select the desired channel rate: 64k, 128k 192k, 384k or "keep each stream's existing rate".
- Select the customize box if you wish to add custom audio encoder options or specifiy a custom file suffix.
- Text Areas for custom audio options and custom suffix will appear if check box is checked otherwise these fields are hidden.

