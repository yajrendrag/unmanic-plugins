
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
