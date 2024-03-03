
**<span style="color:#56adda">0.0.30</span>**
- fix keep undefined audio_streams_list list builder - improper grouping on last 'or' term

**<span style="color:#56adda">0.0.29</span>**
- fix keep undefined audio_streams_list list builder - last time should have been an 'or'

**<span style="color:#56adda">0.0.28</span>**
- fix fail safe function - it was only working when the config list was shorter than streams list

**<span style="color:#56adda">0.0.27</span>**
- fix fail safe function in worker process
- add iso639 module to convert all language tags to is 639.2b for comparison purposes so user doesn't have to specify both 2 and 3 char language codes
- change fail safe test to find all configured languages are present in the file
- fix mapper.stream_encoding so no extraneous stream copies are in generated ffmpeg command
- fix mapped languages edge case in keep_languages when * is specified and language tags are empty list

**<span style="color:#56adda">0.0.26</span>**
- add an optional fail safe check to prevent unintentional deletion of all audio or subtitle streams - option is on by default

**<span style="color:#56adda">0.0.25</span>**
- fix issue of no audio streams in resulting file when '*' selected and user checked keep undefined

**<span style="color:#56adda">0.0.24</span>**
- fix '*' selector to select all languages to keep

**<span style="color:#56adda">0.0.23</span>**
- fix keep_langues streams_list list generator from falsely removing languages when no title tag exists

**<span style="color:#56adda">0.0.22</span>**
- fix missing character in keep_languages causing error upon loading plugin

**<span style="color:#56adda">0.0.21</span>**
- add option to remove commentary audio streams identified by "commentary" (or "Commentary") in audio title tag

**<span style="color:#56adda">0.0.20</span>**
- change copy streams to copying per stream to a single '-c copy' argument to ffmpeg
- this allows pgs subtitle streams to be copied - copying by stream for pgs subs seems to not work

**<span style="color:#56adda">0.0.19</span>**
- fix keep_languages function to test for non-existent language tags
- change keep_undefined to only include streams without tags or without language tags 

**<span style="color:#56adda">0.0.18</span>**
- fix same_streams function to test for non-existent language tags

**<span style="color:#56adda">0.0.17</span>**
- add code to match all streams; enter * in plugin config language field(s) to keep all streams of desired type

**<span style="color:#56adda">0.0.16</span>**
- fix duplicate stream copying in keep undefined
- modify keep_languages to use exact streams instead of language metadata based stream copying

**<span style="color:#56adda">0.0.15</span>**
- fix bug in keep_undefined by refactoring & properly identify specific audio/subtitle stream being mapped and copied

**<span style="color:#56adda">0.0.14</span>**
- fix file_streams_already_kept to remove reference to unused option - ignore_previously_processed

**<span style="color:#56adda">0.0.13</span>**
- fix logger reference to keep_streams vs remove_streams

**<span style="color:#56adda">0.0.12</span>**
- include use of .unmanic file to track files whose streams were previously kept by this plugin to prevent re-adding task to task queue

**<span style="color:#56adda">0.0.11</span>**
- add option to keep streams with no language tags or undefined values

**<span style="color:#56adda">0.0.10</span>**
- fix broken filter from previous step

**<span style="color:#56adda">0.0.9</span>**
- add filter to remove language from configured languages if it doesn't appear in any of a file's streams

**<span style="color:#56adda">0.0.8</span>**
- fix additional file test for duplicate language streams

**<span style="color:#56adda">0.0.7</span>**
- correct logger identification

**<span style="color:#56adda">0.0.6</span>**
- add additional file test to skip file if all configured streams are the only streams present in file

**<span style="color:#56adda">0.0.5</span>**
- correct verbiage in config options to show multiple languages can be accepted

**<span style="color:#56adda">0.0.4</span>**
- fix keep function stream_encoding additions

**<span style="color:#56adda">0.0.3</span>**
- update stream encodings & mappings to only map & copy specifc streams

**<span style="color:#56adda">0.0.2</span>**
- update metadata maps to use optional map syntax

**<span style="color:#56adda">0.0.1</span>**
- Process audio and subtitles
- Based on Remove Streams by Language v0.0.5
