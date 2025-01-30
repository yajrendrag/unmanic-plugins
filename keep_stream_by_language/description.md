
#### Notice
:::important
This plugin now includes a fail-safe option to prevent unintentional deletion of all audio or all subtitles or both.  The plugin checks to ensure that file contains some streams with language tags matching
the configured languages to keep.  If the intersection of configured languages to remove and language tags in the file is the null set, without this option enabled, all of the streams of that type will
be removed.  This is an optional setting - it is on by default.
:::

This plugin will remove all audio or subtitle streams if the configured languages do not match any audio or any subtitle streams, respectively.

##### Configuration Options

- Enter a comma delimited list of audio language codes and a comma delimited list of subtitle language codes to search for during library scans and new file event triggers - only streams matching these langauges are kept - all other streams are removed.
- You can enter * for the language code in one of the two stream types and it will keep all langauges for that stream type.  This is useful, for example, if you want to keep a given audio language and keep all subtitles (or vice versa)
- Keep Commentary - unchecking this will remove commentary streams regardless of it's language code, if any
- keep undefined will keep all undefined or untagged language code streams
- fail safe - if checked, this option will prevent the unitentional removal of all streams of each type (audio, subtitle) if the languages to remove does not intersect with any languages in the file.  If the fail safe is checked and the the check shows the
intersection of configured languages and actual stream languages to be null, the file will be skipped.  If a given stream type is configured to keep all languages (* setting) OR the file doesn't contain any of a particular stream type, that stream type will 
not trigger the fail safe.  If you checked the fail safe, it's also recommended to check the keep undefined option too.

Three letter language codes should be used where applicable.

---

#### Examples:

###### <span style="color:magenta">Keep English Audio and Spanish Subtitles, remove all commentary streams, remove any untagged language streams</span>
```
eng
spa
Keep Commentary - unchecked
Keep Undefined - unchecked
```

