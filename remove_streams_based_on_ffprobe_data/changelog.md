
**<span style="color:#56adda">0.0.7</span>**
- fix string function parens in 0.0.6 fix
- add disposition so can remove streams identified as commentary streams (comment=1 in disposition section)

**<span style="color:#56adda">0.0.6</span>**
- make the comparison string based so strings_to_remove doesn't fail trying to compare a number as string from input to a number read from ffprobe, e.g., channels

**<span style="color:#56adda">0.0.5</span>**
- add '.lower()' to end of 'probe_streams[i]["tags"][probe_field[j].lower()]' in order to get the result be all lower case for test

**<span style="color:#56adda">0.0.4</span>**
- add -strict -2 to ffmpeg command to accommodate what may be experimental features for some containers

**<span style="color:#56adda">0.0.3</span>**
- add test for presence of "tags" in streams_to_remove statement in stream_has_ffprobe_data function
- add lower() function to guard against user entering caps in field names

**<span style="color:#56adda">0.0.2</span>**
- fix error in logger line to remove extra output reference

**<span style="color:#56adda">0.0.1</span>**
- Initial version
- Based on ignore files based on metadata
