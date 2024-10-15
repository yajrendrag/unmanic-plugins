
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
