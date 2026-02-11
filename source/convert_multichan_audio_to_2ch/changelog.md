
**<span style="color:#56adda">0.0.26</span>**
- correct errored name in call to function find_def_lang_stream

**<span style="color:#56adda">0.0.25</span>**
- try installing langcodes with requirements.txt

**<span style="color:#56adda">0.0.24</span>**
- allow a prioritized list of language codes to be specified for marking the default audio stream
- finds the 2 channel stream that has a language matching the highest priority (assumes list is sorted from highest to lowest priority) language from the list of default audio languages
- languages can be speciified using 2 or letter codes - Python's langcodes module is used to match language codes so either code format will match whatever is in the file
- fixed broken match logic
- if no 2 channel stream language matches any of the list of supplied default languages, no stream is marked as the default audio stream.  ffmpeg's behavior should use audio stream 0 as
  the default audio stream 0 in this case

**<span style="color:#56adda">0.0.23</span>**
- streams_to_stereo_encode should return streams as a number

**<span style="color:#56adda">0.0.22</span>**
- copy paste error in probe_streams index variable

**<span style="color:#56adda">0.0.21</span>**
- fix typo in non_aac_streams - missing 's'

**<span style="color:#56adda">0.0.20</span>**
- add normalization option
- add in multichannel streams when converting non-aac streams

**<span style="color:#56adda">0.0.19</span>**
- fix stream index in new code to use audio index and not absolute stream number

**<span style="color:#56adda">0.0.18</span>**
- add missing finish to build of ffmpeg_args in new code to handle when no mc streams exist/selected

**<span style="color:#56adda">0.0.17</span>**
- fix dumb mistake on function name

**<span style="color:#56adda">0.0.16</span>**
- add file test to allow plugin to convert all streams to aac even if there are no matching multichannel streams
 
**<span style="color:#56adda">0.0.15</span>**
- change streams += to streams.append - with integers += breaks string into string of each digit once over 2 characters

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
