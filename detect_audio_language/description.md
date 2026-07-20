
##### Description

This plugin detects a stream's audio language and adds a language tag if the stream has no tag or if it's tagged as unknown.

Uses OpenAI's Whisper Speech Recognition

https://github.com/openai/whisper
https://openai.com/index/whisper/

##### Configuration

#### <span style="color:blue">process_as_multilingual_audio_file</span>
labels the stream with the most frequently observed language.  Useful if source is a recording containing commercials in a native language and the stream audio is in a different language.  Can also be used
when there are multiple languages in the actual source, though it's normally recommended to label the stream as 'mul' and place the observed languages spelled out in the title.

#### <span style="color:blue">force_cpu</span>
The plugin defaults to using an nvidia GPU, but if this option is checked it will bypass the GPU and use the CPU for detection.  The plugin is checking 6 randomly selected, 30 second audio samples, so this
doesn't place a huge burden on the CPU and still executes very fast.  it should be selected if you do not have an nvidia GPU or if your GPU is low on memory.  There are known issues with Whisper not releasing
GPU memory until the calling process (unmanic) terminates.  this will avoid this issue.

#### <span style="color:blue">tag_style</span>
Version 1.0 migrated to langcodes language code library which is based on IETF codes (subsumes ISO 639).  Select whether you prfer 2 letter or 3 letter language codes for your language code tag.

:::important
This plugin is installed using the init system and whisper is pip installed as part of the the plugin installation.  This means that at the time the plugin is installed, whisper is not necessarily
operational, so unmanic should be restarted after this plugin is installed
:::
