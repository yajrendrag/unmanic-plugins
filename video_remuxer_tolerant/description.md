---

This plugin will remux your files to the configured output video container.

It will attempt to transcode any streams not supported by the configured output container.

If the stream is unable to be transcoded, this plugin will remove that stream.

This is a variant of the official [Remux Video Files](https://github.com/Unmanic/plugin.video_remuxer) plugin
that is more tolerant of damaged or poorly timestamped input (for example, broadcast `.ts` recordings).
It adds the following FFmpeg input options in front of `-i`:

- `-fflags +genpts+discardcorrupt` - generate missing presentation timestamps and discard corrupt packets.
- `-err_detect ignore_err` - ignore decoding errors instead of aborting.

---

##### Additional Information:

:::tip
Ensure that your container already supports the streams contained in the source file.
Different containers support different stream codecs.
Especially note subtitle streams. To avoid issues with subtitles, consider also using a Plugin to strip subtitles from the file prior to remuxing.
:::
