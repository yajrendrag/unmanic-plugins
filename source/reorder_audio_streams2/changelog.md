
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
