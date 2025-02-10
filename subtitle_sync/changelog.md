
**<span style="color:#56adda">0.0.10</span>**
- correct mimetype additions to include the '.'
- initialize astream_lang_index

**<span style="color:#56adda">0.0.9</span>**
- return the audio stream index and not the absolute stream index in matching_astream_in_video_file

**<span style="color:#56adda">0.0.8</span>**
- modify basefile & lang parsing in get_sub_lang function to accommodate '.'s in other parts of pathname

**<span style="color:#56adda">0.0.7</span>**
- remove globbing in get_sub_lang function - just do difflib on basefile & abspath difference

**<span style="color:#56adda">0.0.6</span>**
- accommodate sdh tag between lang tag and srt suffix in get_sub_lang function

**<span style="color:#56adda">0.0.5</span>**
- add error checking of probe in file_is_subtitle function

**<span style="color:#56adda">0.0.4</span>**
- install ffs with init.d script instead of requirements.txt file
- fix language comparator to use iso639 match to handle cases where configured
  language and actual subtitle language are a mix of 2 and 3 letters

**<span style="color:#56adda">0.0.3</span>**
- fix progress parser
- fix type variable name to not override builtin function
- fix typo preferred_audioa_astream -> preferred_audio_astream

**<span style="color:#56adda">0.0.2</span>**
- fix typo: languagas -> languages

**<span style="color:#56adda">0.0.1</span>**
- Initial version
