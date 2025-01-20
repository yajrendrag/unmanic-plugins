
**<span style="color:#56adda">0.0.41</span>**
- remove PySceneDetect & revert to just generating frames based on window tims

**<span style="color:#56adda">0.0.40</span>**
- added debug output of iteration counter
- fixed window_size calculation to make it grow by 3 minutes
- changed frame capture rate to 2 frames per second

**<span style="color:#56adda">0.0.39</span>**
- added iteration to auto expand window up to 2x
- added code to use gpu accelerated decode on frame capture

**<span style="color:#56adda">0.0.38</span>**
- fix window start calcs
- fix userdata settings getter

**<span style="color:#56adda">0.0.37</span>**
- add scene list output to debug log

**<span style="color:#56adda">0.0.36</span>**
- add error handling to get_credits_start_and_end function

**<span style="color:#56adda">0.0.35</span>**
- completely new credits detection function originally introduced in v0.0.21
- based on PySceneDetect
- also uses credit words dictionary located in /config/

**<span style="color:#56adda">0.0.34</span>**
- syntax error

**<span style="color:#56adda">0.0.33</span>**
- typo in variable name lastfile -> firstfile

**<span style="color:#56adda">0.0.32</span>**
- ensure lastfile is after firstfile in density calcs

**<span style="color:#56adda">0.0.31</span>**
- fix fix window_start and window_end to round to nearest second so later str() will not error out

**<span style="color:#56adda">0.0.30</span>**
- protect against TypeError in falseend

**<span style="color:#56adda">0.0.29</span>**
- fix window_start and window_end to allow using fractional minutes values from slider changes in 0.0.23 below
- fix lastfile2 so it calculates without error if it reaches the end of the density array

**<span style="color:#56adda">0.0.28</span>**
- fix typo in lastfile2

**<span style="color:#56adda">0.0.27</span>**
- try detecting an false positive of gap in credits erroneously signifying and end of credits

**<span style="color:#56adda">0.0.26</span>**
- do frame capture every second instead of every 2 seconds

**<span style="color:#56adda">0.0.25</span>**
- create a character density array to determine start and end of credits

**<span style="color:#56adda">0.0.24</span>**
- use library data to get path info so not wasting transfer time on multiepisode file back to library

**<span style="color:#56adda">0.0.23</span>**
- make window size for credits split method adjustable in .1 minute increments

**<span style="color:#56adda">0.0.22</span>**
- use cache path for multiepisode source in mkvmerge command for credits method

**<span style="color:#56adda">0.0.21</span>**
- new split method of detecting ending credits text

**<span style="color:#56adda">0.0.20</span>**
- allow fine tuning to adjust the episode end time further than the cumulative run time

**<span style="color:#56adda">0.0.19</span>**
- fixed 2nd recurrence of NoneType error from v0.0.16

**<span style="color:#56adda">0.0.18</span>**
- create black scene only fine tune option for tmdb
- fix error in try block exception handling for valid silence/black detection intervals introduced in v0.0.16 

**<span style="color:#56adda">0.0.17</span>**
- typo in if statement checking intervals

**<span style="color:#56adda">0.0.16</span>**
- check for valid silence and black intervals; otherwise skip current line in sb detection file

**<span style="color:#56adda">0.0.15</span>**
- add silence slider to config for tmdb lookup option

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
