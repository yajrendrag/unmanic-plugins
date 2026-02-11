
#### Notice
:::important
This plugin now includes a fail-safe option to prevent unintentional deletion of all audio streams.  This is a change - it's only preserving audio - not subtitles.  The plugin checks to ensure that file contains
some audio streams with language tags matching the configured audio languages to keep.  If the intersection of audio configured languages to remove and audio language tags in the file is the null set, then without
this option enabled, all of the audio streams will be removed.  This is an optional setting, but is on by default.
:::

This plugin will remove all audio or subtitle streams if the configured languages do not match any audio or any subtitle streams, respectively, unless the fail-safe option is checked.

##### Configuration Options

- Enter a comma delimited list of audio language codes and a comma delimited list of subtitle language codes to search for during library scans and new file event triggers - only streams matching these langauges are kept - all other streams are removed.
- You can enter * for the language code in one of the two stream types and it will keep all langauges for that stream type.  This is useful, for example, if you want to keep a given audio language and keep all subtitles (or vice versa)
- Keep Commentary - unchecking this will remove commentary streams regardless of it's language code, if any
- keep undefined will keep all undefined or untagged language code streams
- fail safe - if checked, this option will prevent the unitentional removal of all streams of each type (audio, subtitle) if the languages to remove does not intersect with any languages in the file.  If the fail safe is checked and the the check shows the
intersection of configured languages and actual stream languages to be null, the file will be skipped.  If a given stream type is configured to keep all languages (* setting) OR the file doesn't contain any of a particular stream type, that stream type will 
not trigger the fail safe.  If you checked the fail safe, it's also recommended to check the keep undefined option too.
- reorder_kept - if checked, this will reorder the kept audio streams by making the first stream(s) in the file, those streams that match the first audio language listed above; audio stream 0 will also have default disposition set.
- Set Multichannel or 2 channel - this option is only visible if reordering kept streams.  Specify if you prefer 2 channel or multichannel to be the default audio when the file has more than one stream that matches the first language tag in the list of audio languages.

:::note
Plugin now uses Python's langcodes module to check for valid language codes.  langcodes uses BCP 47 (IETF RFC 5646) to identify language codes - this subsumes ISO 639, which the plugin used prior to langcodes.  langcodes has a 
larger set of language  codes recognized by IETF.  You do not need to list both 2 letter and 3 letter versions of the code - if you specify `en`, and the actual code in the file is `eng`, it will still match and vice versa.
:::
---

#### Examples:

###### <span style="color:magenta">Keep English Audio and Spanish Subtitles, remove all commentary streams, remove any untagged language streams, do not use fail-safe.  reorder audio streams to put English audio first and if there are more than one english audio streams, prefer the 2 channel to be the first and default audio stream</span>
```
eng
spa
Keep Commentary - unchecked
Keep Undefined - unchecked
fail_safe - unchecked
reorder_kept - checked
2 channel preferred
```

