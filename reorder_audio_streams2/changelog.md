
**<span style="color:#56adda">0.0.25</span>**
- stream indicies in copy encoder were incorrect - should have applied enumeration on new_audio_position to determine output stream index
- remove all c:x:y copy and use a single -c copy so that determining new stream index in output file isn't required

**<span style="color:#56adda">0.0.24</span>**
- remove the data['add_file_to_pending_tasks'] = False lines (or set them to None instead) so the remaining plugins' file testing will work

**<span style="color:#56adda">0.0.23</span>**
- prevent file from being added to task queue or from being processed if the result would contain no audio streams

**<span style="color:#56adda">0.0.22</span>**
- reversed index correction from version 0.0.21 (it was correct originally) and put astream_order.remove in a try block

**<span style="color:#56adda">0.0.21</span>**
- add file test check so file is skipped (not added to task queue) if the new audio stream order is the same as original
- correct index on additional_audio_position list comprehension in get_old_and_new_order function so that order is correct on additional audio streams

**<span style="color:#56adda">0.0.20</span>**
- fix typo in lib import statement - missing .lib in path to ffmpeg

**<span style="color:#56adda">0.0.19</span>**
- fix submodule to match changed name of plugin

**<span style="color:#56adda">0.0.18</span>**
- fix probe, parser import line to refer to correct plugin name post plugin name change

**<span style="color:#56adda">0.0.17</span>**
- added fix for allowing more than two 3 letter codes per each 2 letter lookup

**<span style="color:#56adda">0.0.16</span>**
- add option to remove streams not configured to be reordered
- to keep any streams with undefined language tags, add 'und' to end of additional languages field
- any streams without any language tags at all in this scenario will be removed

**<span style="color:#56adda">0.0.15</span>**
- added logging for year2 TypeError and skipping year2 for those file conditions

**<span style="color:#56adda">0.0.14</span>**
- fix missing import re and compiled regex expresssion for PTN excess

**<span style="color:#56adda">0.0.13</span>**
- add workaround for PTN parsing incorrect year

**<span style="color:#56adda">0.0.12</span>**
- guard against empty original_language array in altr

**<span style="color:#56adda">0.0.11</span>**
- add all pages from tmdb query

**<span style="color:#56adda">0.0.10</span>**
- rename plugin to reorder_audio_streams2
- make reordering original languages an option

**<span style="color:#56adda">0.0.9</span>**
- fix unique test function results so only used when more than 1 result found
- add test for equal original languages when more than 1 result found - instead of aborting, just return that original language as they are all the same
- fix library file test to implement reordering when original language not found but additional reordering option is checked

**<span style="color:#56adda">0.0.8</span>**
- add fixes for punctuation in titles
- test both title/name and original_title/original_name for unique match
- refactor unique test into dedicated function

**<span style="color:#56adda">0.0.7</span>**
- added filenames to various logger output to make tracing issues easier

**<span style="color:#56adda">0.0.6</span>**
- add a translation code for 2 letter language 'cn' to same as that for 'zh'

**<span style="color:#56adda">0.0.5</span>**
- make original_language list compatible with multiple original languages when 2 letter code translates to different b & t 3 letter codes

**<span style="color:#56adda">0.0.4</span>**
- add title field variable as tmdb movie title elment an tv title element have different field names
- fix iso-639.2 b & t code parser
- fix add to task queue logic which had a potential KeyError

**<span style="color:#56adda">0.0.3</span>**
- fix year reference in formula to treat as string
- add tasks to queue if original language not found, but additional languages set to restore
- change to parse_torrent_title parser - better parsing
- fix language lookup when table has a '/' to separate multiple options for 3 letter codes

**<span style="color:#56adda">0.0.2</span>**
- add tests to ensure original audio stream is actually in file's audio streams before adding to task queue
- add appropriate log messages for these tests

**<span style="color:#56adda">0.0.1</span>**
- Initial version
