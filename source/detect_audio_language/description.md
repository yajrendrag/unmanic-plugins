
##### Description

This plugin detects a stream's audio language and adds a language tag if the stream has no tag or if it's tagged as unknown.

Uses OpenAI's Whisper Speech Recognition

https://github.com/openai/whisper
https://openai.com/index/whisper/

##### Configuration

No configuration is required - the plugin will operate on files that have audio streams tagged with undefined (und) or that
have no audio stream tag at all.

:::important
This plugin is installed using the init system and whisper is pip installed as part of the the plugin installation.  This means that at the time the plugin is installed, whisper is not necessarily
operational, so unmanic should be restarted after this plugin is installed
:::
