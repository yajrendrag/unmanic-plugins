
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

- This plugin converts all audio streams to libopus
---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - High Quality Audio Encoding](https://trac.ffmpeg.org/wiki/Encode/HighQualityAudio)
- opus recommended bit rates:
  - 64k per channel is transparent for stereo
  - for 5.1 and 7.1, 64k per channel is more than sufficient - can probably reduce a little - 5.1@256k and 7.1@450k is considered transparent
--- 

##### Config description:

- bit_rate - set the per channel bit rate to the desired rate - default is 64k
