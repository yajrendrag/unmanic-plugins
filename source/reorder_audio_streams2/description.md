---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Documentation:

For information on the The Movie Database (tmdb):
- [The Movie Database (tmdb)](https://www.themoviedb.org/)

For more information on language codes:
- [language codes](https://en.wikipedia.org/wiki/List_of_ISO_639-2_codes)

---

##### Description:

This plugin provides multiple options to reorder audio streams.  There are 2 checkbox options on the configuration page.  Reordering orginal audio indicates that the original audio for 
a given file will be the first audio stream.  Reordering additional audio languages means that one or more (comma delimited) audio streams can be specified and those audio streams will
be placed in the order listed on the configuration page either as the first audio streams or will be placed behind the original audio stream if both check boxes are checked.

In the case of using original audio, this plugin does a lookup of the original audio language an you will need your own tmdb API - join tmdb and then request an API. The api configuration
has two components - an api_key and an API Read Access Token - you need both.  Configure the plugin with both values - they should be clearly labeled.

The original language is moved to be the first audio language and it's disposition is also set to be the default language and all other language dispositions are set to false.

Additionally you may configure a list of additional languages to reorder - this is a comma delimited list and the plugin will reorder these language streams (in the order the appear in the config screen) after the original language.
All remaining language streams will follow these in the order they originally appeared in the file relative to one another.
Specify these addditional languages as a comma delimited list of languages which are most likely to be 3 letter language codes.

The original audio option and the additional audio option can be used separately or together, but one of them must be checked.
---
### Config description:

#### <span style="color:blue">reorder_original_language</span>
Only check this if you wish to make the original audio language the first audio stream.  Nothing will change if the original audio stream is not uniquely identified or if it's missing from 
the list of audio streams in the file.

#### <span style="color:blue">reorder_additional_audio_streams</span>
Check this if you wish to reorder additional language streams - it can be used with or without checking the reorder original language option.

#### <span style="color:blue">library_type</span>
Select TV or Movies for the library type - the plugin can only process a single content type per library.  This option is only visible if reorder original audio is checked.

#### <span style="color:blue">"tmdb_api_key</span>
Enter your tmdb api_key.  This option is only visible if reorder original audio is checked.

#### <span style="color:blue">"tmdb_api_read_access_token</span>
Enter your tmdb API Read access token (it's a really long string).  This option is only visible if reorder original audio is checked.

#### <span style="color:blue">"Search String</span>
enter a comma delimited list of additional languages to be reordered - this is only visible if you check the reorder_additional_audio_streams option above.
These are likely 3 letter codes, e.g., eng, ger (you can enter with spaces or not - it doesn't matter)
