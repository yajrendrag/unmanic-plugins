---

##### Description:

Remuxes video files to the Matroska (MKV) container using `mkvmerge` from [MKVToolNix](https://mkvtoolnix.download/).
No streams are re-encoded. The command run for each file is:

```
mkvmerge -o <output_file>.mkv <source_file>
```

This plugin is intended for MPEG transport stream recordings (`.ts`, `.m2ts`, `.mts`), but any extension can be configured.

`mkvmerge` is installed automatically into the Unmanic container by this plugin's `init.d` script on container startup.
After installing the plugin, restart the Unmanic container.

##### Pre-checks:

Before a file is queued (and again before it is processed by the worker), the following checks are run.
If any check fails, the file is left untouched and the reason is written to the Unmanic log / worker log.

- The file extension must be one of the configured extensions.
- `mkvmerge` must be installed.
- `mkvmerge -J` must be able to identify the file without errors, and must recognise and support the container format.
- `mkvmerge` must find at least one video track.
- (Optional) The number of video, audio and subtitle streams that `ffprobe` finds must not be greater than the number of tracks `mkvmerge` identifies. This prevents a remux that would silently drop streams `mkvmerge` cannot handle.

---

##### Settings:

###### File extensions to remux
A comma separated list of file extensions that should be remuxed. Default: `ts,m2ts,mts`.

###### Skip files where mkvmerge would drop video/audio/subtitle streams
When enabled, files are skipped if `mkvmerge` would not carry over every video, audio and subtitle stream that `ffprobe` detects.
Streams with no detectable codec (for example, empty PIDs listed in the TS program map) are ignored.

###### Fail the task if mkvmerge exits with warnings
`mkvmerge` exits with code `1` when it finishes with warnings (for example, timestamp discontinuities which are common in broadcast TS recordings).
The output file is still written in this case. By default these warnings are treated as success. Enable this to mark such tasks as failed instead.
