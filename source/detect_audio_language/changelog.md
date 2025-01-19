
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
