
**<span style="color:#56adda">0.1.1</span>**
- add langcodes to requirements.txt

**<span style="color:#56adda">0.1.0</span>**
- update language code library to IETF langcodes from ISO639

**<span style="color:#56adda">0.0.31</span>**
- add option to force_cpu - useful if no nvidia GPU or if encountering issues of GPU memory not being released after plugin runs

**<span style="color:#56adda">0.0.30</span>**
- modify whisper commands to work with ffmpeg produced audio file (moviepy was producing this directly)

**<span style="color:#56adda">0.0.29</span>**
- removed moviepy and just processed files natively with ffmpeg using pytho-ffmpeg

**<span style="color:#56adda">0.0.28</span>**
- set custom version of ffmpeg for moviepy so it uses same ffmpeg version as unmanic

**<span style="color:#56adda">0.0.27</span>**
- added a check for OSError in try except block of tag streams to help identify failed ffmpeg command construction
- added an option to process declared multilingual files by just tagging stream with most detected language across the 6 samples
 
**<span style="color:#56adda">0.0.26</span>**
- added debug output to view output_file name and command in tag_streams

**<span style="color:#56adda">0.0.25</span>**
- fix test of length of detected_languages check - removed return None from elif in case it's not the first lang that has enough sample occurences

**<span style="color:#56adda">0.0.24</span>**
- try adding explicit model deletion and cache emptying to get GPU to release whisper resources

**<span style="color:#56adda">0.0.23</span>**
- fix test of length of detected_languages check as both 2 & 3 are legit lengths
- misc fix of debug string messages

**<span style="color:#56adda">0.0.22</span>**
- in tag_streams configure shutil.rmtree to ignore errors

**<span style="color:#56adda">0.0.21</span>**
- fix init.d to install moviepy 2.1.2 - it was still set to 1.03 after 0.0.19 fix

**<span style="color:#56adda">0.0.20</span>**
- add exception so that CPU only systems can run plugin
- fix get_model while loop so loop index of -1 is detected & tested before use

**<span style="color:#56adda">0.0.19</span>**
- update moviepy to 2.1.2
- select largest model possible on GPU, fall back to medium on CPU if no GPU or insufficient memory
- fix spacing around function to checking number of languages detected
- allow errors in shutil.rmtree

**<span style="color:#56adda">0.0.18</span>**
- relax % of samples needed to match to 66.6%
- added lang detected in sample to debug output

**<span style="color:#56adda">0.0.17</span>**
- fixed description.md file
- relax % of samples needed to match - but double number of samples

**<span style="color:#56adda">0.0.16</span>**
- fix typo in variable name

**<span style="color:#56adda">0.0.15</span>**
- change init.d script to install correct version of moviepy

**<span style="color:#56adda">0.0.14</span>**
- revert to moviepy 1.0.3

**<span style="color:#56adda">0.0.13</span>**
- use mkv extension for temp files
- remote all metadata from temp files
- use unmanic container's ffmpeg binary instead of moviepy's ffmpeg library

**<span style="color:#56adda">0.0.12</span>**
- fixed moviepy install version to 2.0.0 to alleviate api changes

**<span style="color:#56adda">0.0.11</span>**
- added more debug output

**<span style="color:#56adda">0.0.10</span>**
- update moviepy to 2.0 api

**<span style="color:#56adda">0.0.9</span>**
- fix construction of temp video files to use glob

**<span style="color:#56adda">0.0.8</span>**
- fix dir variable in os.remove
- also delete the temp video files created

**<span style="color:#56adda">0.0.7</span>**
- add code to explicitly remove temp wav files as on some systems shutil.rmtree throws an exception if non-empty directory 

**<span style="color:#56adda">0.0.6</span>**
- attribution to OpenAI Whisper Module
- addition of OpenAI Whisper License

**<span style="color:#56adda">0.0.5</span>**
- update description 

**<span style="color:#56adda">0.0.4</span>**
- fix audio file samples to pick 30 second long samples in all cases
- add test to ensure file is >= 10 minutes otherwise samples could be less than 30 seconds

**<span style="color:#56adda">0.0.3</span>**
- reformat ffmpeg_args construction

**<span style="color:#56adda">0.0.2</span>**
- fix ffmpeg line to refer to variable tag_args

**<span style="color:#56adda">0.0.1</span>**
- Initial version
