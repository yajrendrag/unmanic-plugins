]
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin converts multichannel audio streams to stereo audio streams using the native ffmpeg aac encoder or,
if selected, using libfdk_aac (requires ffmpeg 5.x - as of March 2024 unmanic uses ffmpeg 6.0.X)

This Plugin uses 64k per audio channel, so 128 kbps for stereo. 

Over time this plugin has added more features.  It now also:
- optionally leaves the multichannel stream in the file
- allows the stereo stream(s) to be marked as the default audio stream(s).
- requires you to specify a language for the stereo stream(s) when marking the stereo stream(s) as default.
- allows all other, non-aac encoded streams to be encoded with the selected aac encoder. 

In above, stream is written optionally as stream(s) in the event there are multiple stereo audio streams
of the same language.  In this case, multiple streams could be marked as default in which case, which stream
a particular media player selects as default may vary.

If there are no multichannel streams in the file or none identified, the plugin will convert all audio streams to aac if the
option encode_all_2_aac is selected. In this case, if the option set_2ch_stream_as_default is also selected, the plugin will
look for an existing stream (of any number of channels) with a langauge matching the supplied language and set it's default
disposition to true. 
---

##### Documentation:

For information on the available encoder settings:
- [FFmpeg - AAC Encoder](https://trac.ffmpeg.org/wiki/Encode/AAC)

Loudness information:
- [FFmpeg - Loudness Normalization](https://trac.ffmpeg.org/wiki/AudioVolume#LoudnessNormalization)
--- 

### Config description:

#### <span style="color:blue">Encoder Selection</span>
Leave unchecked to select native ffmpeg aac encoder, libfdk_aac requires ffmpeg 5.x

#### <span style="color:blue">encode_all_2_aac</span>
Encodes all streams to the selected aac encoder - not just the stream created as 2 channel.  All kept streams are converted to selected aac encoder.

#### <span style="color:blue">keep_mc</span>
Keeps multichannel stream in the resulting file in addition to stereo stream derived from it

#### <span style="color:blue">set_2ch_stream_as_default</span>
Sets the 2 channel stream to be the default stream

#### <span style="color:blue">default_lang</span>
if the preceeding option is selected, this option becomes visible and you must indicate a language of an existing multichannel stream which, when converted to
2channel, will marked as a default audio stream

#### <span style="color:blue">normalize_2_channel_stream</span>
selecting this option will apply a normalization filter to the 2 channel aac streams.  This is useful when converting multichannel to 2 channel as what is
typical voice range in the center channel seems to sound muddled and low volume after conversion.  The default settings are should be a very good starting
point and most people will not need to modify the settings.  Otherwise, you can modify the settings that will appear below this when this option is enabled.

#### <span style="color:blue">I</span>
Integrated Loudness Target

#### <span style="color:blue">LRA</span>
Loudness Range

#### <span style="color:blue">TP</span>
Maximum True Peak

:::note
This plugin will create a stereo aac or libfdk_aac stereo stream from each multichannel
audio stream. The original multichannel streams will be removed unless you opt to keep the multichannel
stream via configuration option.  If encoding all non-aac audio streams to aac and any multichannel stream
is > 6 channels (e.g., TrueHD), it will be reduced to 6 channels and encoded with aac.
:::
