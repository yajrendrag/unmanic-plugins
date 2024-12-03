
**<span style="color:#56adda">0.0.14</span>**
- add option to encode all non-aac encoded streams to aac with selected encoder
- this allows this plugin to act as single plugin for aac encoding as well as creating 2 channel aac streams from multichannel audio streams

**<span style="color:#56adda">0.0.13</span>**
- add option to reorder stereo stream(s) to first audio stream(s)
- removed original disposition from other audio streams if setting stereo as default stream

**<span style="color:#56adda">0.0.12</span>**
- test for presence of title field for commentary

**<span style="color:#56adda">0.0.11</span>**
- fix streams list variable in commentary check

**<span style="color:#56adda">0.0.10</span>**
- add option to set 2 channel stereo stream as default stream
- along with above specify an option for stream language to use as default in case of multiple 2 channel streams
- ensure commentary streams are not counted as existing stereo streams

**<span style="color:#56adda">0.0.9</span>**
- fix title metadata

**<span style="color:#56adda">0.0.8</span>**
- add title tag to audio stream - unlikely this will work in mp4 files as there is no standard title tag for audio streams in mp4 containers

**<span style="color:#56adda">0.0.7</span>**
- add another try-except block for audio streams without bit_rate param when not keeping mc stream

**<span style="color:#56adda">0.0.6</span>**
- remove setting data['add_file_to_pending_tasks'] = False to allow other plugins to continue

**<span style="color:#56adda">0.0.5</span>**
- add try-except block to catch audio streams without bit_rate parameter

**<span style="color:#56adda">0.0.4</span>**
- add option to keep or discard multichannel streams
- changed default encoder to libfdk_aac
- set rate for stereo to 2x channel rate of source multichannel stream

**<span style="color:#56adda">0.0.3</span>**
- add check for existing stereo stream of multichannel stream languages

**<span style="color:#56adda">0.0.2</span>**
- use correct plugin name in logger message

**<span style="color:#56adda">0.0.1</span>**
- initial release
- based on add_extra_stereo_audio
