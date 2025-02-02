
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

- This plugin adds an additional multichannel audio stream from an existing multichannel DD+ or TrueHD stream
- The encoder is a configuration option of either libfdk_aac (requires ffmpeg 5.1 or greater) or ac3
- This Plugin uses the existing multichannel bit rate if less than 640k or 640k otherwise.

---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - High Quality Audio Encoding](https://trac.ffmpeg.org/wiki/Encode/HighQualityAudio)
--- 

### Config description:

#### <span style="color:blue">Encoder Selection</span>
Leave unchecked to select all files or check to restrict to only select 4k files
Select audio encoder of ac3 or libfdk_aac

:::note
This plugin will create a multichannel audio stream from the existing multichannel
DD+ or TrueHD stream; it will use whichever stream has the largest number of channels.. The original multichannel streams will be left intact.
:::
