
**<span style="color:#56adda">0.0.18</span>**
- modified description.md

**<span style="color:#56adda">0.0.17</span>**
- make whisper device configurable
- make whisper model configurable
- let plugin modify model and device if configured model is too large for available resources, including ability to downgrade to cpu device

**<span style="color:#56adda">0.0.16</span>**
- fix post processor cleanup of /tmp/unmanic

**<span style="color:#56adda">0.0.15</span>**
- fix tmp directory

**<span style="color:#56adda">0.0.14</span>**
- explicitly find audio stream
- write temp audio file to /tmp/unmanic
- run whisper on temp audio file
- delete temp audio files when done

**<span style="color:#56adda">0.0.13</span>**
- add shutil.copy2 instead of os.rename to avoid invalid cross-device link error

**<span style="color:#56adda">0.0.12</span>**
- added logger.debug
- moved original_file_path assignment statement to avoid using before defined

**<span style="color:#56adda">0.0.11</span>**
- write srt file to the destination directory

**<span style="color:#56adda">0.0.10</span>**
- use lang names in post processor to determine if configured lang is in file so that srt file is saved with lang code

**<span style="color:#56adda">0.0.9</span>**
- change language code to language name in whisper command 

**<span style="color:#56adda">0.0.8</span>**
- add iso639 module to allow specifying any type of code and translate to language name
- test to ensure language name is supported by whisper model, otherwise abort

**<span style="color:#56adda">0.0.7</span>**
- fix parser to produce integer progress value (ie, no decimal) to better fit in GUI

**<span style="color:#56adda">0.0.6</span>**
- fix logger plugin reference

**<span style="color:#56adda">0.0.5</span>**
- fix post processor to recognize when audio stream doesn't match configured language and use a numbered subtitle output file

**<span style="color:#56adda">0.0.4</span>**
- fix progress time_str to account for variable length time strings
- round progress percentage to 1 decimal

**<span style="color:#56adda">0.0.3</span>**
- & -> and

**<span style="color:#56adda">0.0.2</span>**
- set first_audio_stream index

**<span style="color:#56adda">0.0.1</span>**
- Initial version
