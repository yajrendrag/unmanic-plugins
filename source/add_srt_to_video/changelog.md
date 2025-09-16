
**<span style="color:#56adda">0.1.0</span>**
- remove homegrown lang_codes list and migrate to langcodes library
- if a subtitle file has a non-standard stream, it just skips those streams rather than aborting
- only deletes subtitle streams if post processor detects that a subtitle stream exists in the file with that language
- adds an option to allow the user to specify whether they prefer 2 letter codes or 3 letter codes to be written as the language tag

**<span style="color:#56adda">0.0.15</span>**
- change lang parser to just pick the first non blank characters after the first dot as the language - this allows forms of .lang.srt or .lang.other_code.srt

**<span style="color:#56adda">0.0.14</span>**
- reverse logic in check_srt so it skips the bad srt files

**<span style="color:#56adda">0.0.13</span>**
- pull check_sub into it's own loop as the stream indicies get out of sync when skipping files in the main loop

**<span style="color:#56adda">0.0.12</span>**
- fix check_sub to fix encode muxer format - suffix passed in has preceeding '.'

**<span style="color:#56adda">0.0.11</span>**
- add error handling to check_sub if encode test fails

**<span style="color:#56adda">0.0.10</span>**
- correct 'suffix' to 'sfx' in check_sub if statement

**<span style="color:#56adda">0.0.9</span>**
- add check_sub function to verify subtitle will encode before adding to ffmpeg_subtitle_args; if error, subtitle file is skipped.

**<span style="color:#56adda">0.0.8</span>**
- change worker process to reference the original source file path to match srt files to since file_in will be in the cache and no srt files there

**<span style="color:#56adda">0.0.7</span>**
- fix loop in post processor so list stays constant while deleting files

**<span style="color:#56adda">0.0.6</span>**
- added capability to keep any existing subtitles

**<span style="color:#56adda">0.0.5</span>**
- glob.escaped all basefiles to protect against special characters in the path name

**<span style="color:#56adda">0.0.4</span>**
- moved the deletion of the srt files to a post processing routine in order to test task success before deletion

**<span style="color:#56adda">0.0.3</span>**
- fix lang3 to isolate a single 3 letter code when a two letter code translates to more than 1 code
- fix 'no' in lang_codes to add selection asterisk for one of the 3 letter codes

**<span style="color:#56adda">0.0.2</span>**
- fix stray quote in line 1
- correct language code to lang3 in ffmpeg_subtitle_args var

**<span style="color:#56adda">0.0.1</span>**
- Initial version
