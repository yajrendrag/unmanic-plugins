
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

- This plugin adds an additional multichannel (or stereo - see 2 chnnel option below) audio stream from an existing multichannel DD+ or TrueHD stream (or stereo - see 2 channel option below)
- The encoder is a configuration option of either libfdk_aac (requires ffmpeg 5.1 or greater) or ac3
- This Plugin uses the existing multichannel bit rate if less than 640k or 640k otherwise.

---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - High Quality Audio Encoding](https://trac.ffmpeg.org/wiki/Encode/HighQualityAudio)
--- 

### Config description:

#### <span style="color:blue">skip_files_less_than_4k_resolution</span>
Leave unchecked to select all files or check to restrict to only select 4k files

#### <span style="color:blue">Encoder Selection</span>
Select audio encoder of ac3 or libfdk_aac

#### <span style="color:blue">replace_original</span>
Replaces original stream rather than adding a new stream

#### <span style="color:blue">allow_2_ch_source</span>
Allows 2 channel sources to be used to create a stereo ac3 or libfdk_aac version of a 2 channel source, dts, truehd, or eac3 stream.  If both a 2 channel and multichannel
version of the same language stream is found, the stream with the greatest number of channels will be used as the source.

:::note
This plugin will create a multichannel audio stream from the existing multichannel
DD+ or TrueHD stream; it will use whichever stream has the largest number of channels.. The original multichannel streams will be left intact unless
the replace_original option is checked.
:::
