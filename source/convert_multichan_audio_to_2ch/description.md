
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin converts multichannel audio streams to stereo audio streams using the native ffmpeg aac encoder or,
if selected, using libfdk_aac (requires ffmpeg 5.x)

This Plugin uses 64k per audio channel, so 128 kbps for stereo. 

---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - AAC Encoder](https://trac.ffmpeg.org/wiki/Encode/AAC)

--- 

### Config description:

#### <span style="color:blue">Encoder Selection</span>
Leave unchecked to select native ffmpeg aac encoder, libfdk_aac requires ffmpeg 5.x

:::note
This plugin will create a stereo aac or libfdk_aac stereo stream from each multichannel
audio stream. The original multichannel streams will be removed.
:::
