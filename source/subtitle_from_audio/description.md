
##### Description
This plugin will create an srt subtitle file from a video file's selected audio stream.

##### Reference
Uses OpenAI's Whisper Speech Recognition

https://github.com/openai/whisper
https://openai.com/index/whisper/

##### Configuration
- specify the language of the audio stream to save as an srt stream
- choose action to take if the specified language stream does not exist
- specify whisper model - models are shown as whisper model name - required VRAM - relative speed
- whisper device - CUDA or CPU.  CPU will be very slow.

:::warning
This plugin is not compatible with linking as the remote link will not have access to the original source file's directory.
:::
