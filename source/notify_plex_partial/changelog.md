
**<span style="color:#56adda">0.0.10</span>**
- fixed incorrect section_id calculation
- refactored update_plex to include section_id calculation

**<span style="color:#56adda">0.0.9</span>**
- added more debug output
- added better error messaging especially related to unauthorized errors from plexapi
- fixed unmanic_dir and host_dir variable definitions which were reversed
- added BeautifulSoup4 to parse text output from requests results

**<span style="color:#56adda">0.0.8</span>**
- add debug output to update_plex

**<span style="color:#56adda">0.0.7</span>**
- modified analyze to comment out the year filter with an explanatory note in case an example comes up where it's needed

**<span style="color:#56adda">0.0.6</span>**
- added debug output to inspect analyze function

**<span style="color:#56adda">0.0.5</span>**
- rewrote analyze function

**<span style="color:#56adda">0.0.4</span>**
- add option to analyze media file

**<span style="color:#56adda">0.0.3</span>**
- add test to see if destination file exists - otherwise plex can't be notified by destination path

**<span style="color:#56adda">0.0.2</span>**
- add code to find library_id

**<span style="color:#56adda">0.0.1</span>**
- Initial version
- based on v0.0.5 of notify_plex
