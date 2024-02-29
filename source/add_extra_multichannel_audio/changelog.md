
**<span style="color:#56adda">0.0.14</span>**
- fix map command missing leading '-'

**<span style="color:#56adda">0.0.13</span>**
- fix stream title to match encoder selected
- fix formatting on encoder selection menu
- added option to remove original audio stream - new audio gets added in original stream's location

**<span style="color:#56adda">0.0.12</span>**
- fix logger and import lines to reflect name change

**<span style="color:#56adda">0.0.11</span>**
- fix encoder selection menu

**<span style="color:#56adda">0.0.10</span>**
- add a configuration option to encode with libfdk_aac or ac3
- renamed plugin add_extra_multichannel_audio

**<span style="color:#56adda">0.0.9</span>**
- readded fix for finding existing ac3 stream of same language as lossless stream and not adding a new stream in that eventuality

**<span style="color:#56adda">0.0.8</span>**
- delete stray character

**<span style="color:#56adda">0.0.7</span>**
- fixed test for finding existing ac3 stream
- commented them all out for now as if there is no ac3 stream and also no language tag, it still may find nothing..

**<span style="color:#56adda">0.0.6</span>**
- add test to see if a 6 channel ac3 stream already exists with language matching that of selected TrueHD, eac3, or DTS audio - if so skip file
- add correct stream title metadata for added ac3 audio stream
- add fix to remove unnecessary mp4 metadata chapter title stream when output path suffix is mp4

**<span style="color:#56adda">0.0.5</span>**
- fix non-existent streams reference - change to probe_streams

**<span style="color:#56adda">0.0.4</span>**
- fix probe_streams reference

**<span style="color:#56adda">0.0.3</span>**
- fix total audio streams count

**<span style="color:#56adda">0.0.2</span>**
- added test to select only truehd or eac3 multichannel streams to encode

**<span style="color:#56adda">0.0.1</span>**
- initial release
- based on add_extra_stereo_audio
