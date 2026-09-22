
**<span style="color:#56adda">0.0.10</span>**
- changed to use .unmanic file for tracking since mp4 containers don't write the ENCODER tag

**<span style="color:#56adda">0.0.9</span>**
- added force processing option

**<span style="color:#56adda">0.0.8</span>**
- set channels to 6 if channels > 6

**<span style="color:#56adda">0.0.7</span>**
- add 'ac' parameter to ffmpeg command to ensure proper channel_layout field for compatiability with normalization plugin to avoid unsupported channel layout error

**<span style="color:#56adda">0.0.6</span>**
- fix multiline format issue

**<span style="color:#56adda">0.0.5</span>**
- add debug logger output for ENCODER value

**<span style="color:#56adda">0.0.4</span>**
- fix test stream functiojn to test tags for ENCODER value containing 'libfdk_aac'

**<span style="color:#56adda">0.0.3</span>**
- fix library call in plugin.py

**<span style="color:#56adda">0.0.2</span>**
- use yajrendrag lib/ffmpeg helper lib - allows extra encoders in custom options

**<span style="color:#56adda">0.0.1</span>**
- based off of v0.0.5 of AAC encoder
- modified original AAC encoder to use libfdk_aac - which is in jellyfin_ffmpeg5
