
**<span style="color:#56adda">0.0.14</span>**
- modify tmdb fine tune to use black-silence overlap scene interval instead of black scene only

**<span style="color:#56adda">0.0.13</span>**
- fix PTN accompanying regex related to detecting '_' as episode seperator

**<span style="color:#56adda">0.0.12</span>**
- modify get_parsed_info to detect '_' as episode separator

**<span style="color:#56adda">0.0.11</span>**
- add codec name as option for split files

**<span style="color:#56adda">0.0.10</span>**
- redefine split_file to use PTN instead of regex
- filter out [] in the name of the season directory
- change first season directory pattern option to title SxxEyy-Ezz - resolution - quality

**<span style="color:#56adda">0.0.9</span>**
- add output directory name pattern options
- use PTN for parsing filename instead of regex

**<span style="color:#56adda">0.0.8</span>**
- add option to keep or delete original, multiepisode file
- add split method of using silence and black scene detection - uses overlap of the 2 to identify episode change
- add split method of using tmdb episode runtime lookup
- change time split method to just use an average based on multiepisode file duration and number of episodes detected in file name

**<span style="color:#56adda">0.0.7</span>**
- add series title to season subdirectory

**<span style="color:#56adda">0.0.6</span>**
- create season subdirectory

**<span style="color:#56adda">0.0.5</span>**
- add missing LICENSE file

**<span style="color:#56adda">0.0.4</span>**
- fixed regex to allow for optional E in front of trailing episode number

**<span style="color:#56adda">0.0.3</span>**
- fix split file naming to simply rename SxxEyy-zz to SxxEyy, SxxEyy+1,... SxxEzz
- file must be a multi episode file and match the multiepisode format above in the name of the file

**<span style="color:#56adda">0.0.2</span>**
- fixed incorrect variable in file test section

**<span style="color:#56adda">0.0.1</span>**
- initial release
