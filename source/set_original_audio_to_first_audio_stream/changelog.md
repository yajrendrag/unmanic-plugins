
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
