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

This plugin operates on a single audio stream.  It's intended purpose is to set the language metadata of the single audio stream to the original language as returned by tmdb.
Thus, it requires a tmdb account and associated API keys.  The idea here is that you feel sufficiently confident that the single audio stream in the file matches the original audio
of the film or show.  If you are not fairly confident that the language of the audio stream will match the original language, you risk mislabeling the audio.

You need to set the library type to movies or tv so the lookup operates on the correct database.

---
##### Config description:

#### <span style="color:blue">library_type</span>
Select TV or Movies for the library type - the plugin can only process a single content type per library.  This option is only visible if reorder original audio is checked.

#### <span style="color:blue">"tmdb_api_key</span>
Enter your tmdb api_key.  This option is only visible if reorder original audio is checked.

#### <span style="color:blue">"tmdb_api_read_access_token</span>
Enter your tmdb API Read access token (it's a really long string).  This option is only visible if reorder original audio is checked.

#### <span style="color:blue">tag_style</span>
Version 0.0.3 migrated to langcodes language code library which is based on IETF codes (subsumes ISO 639).  Select whether you prfer 2 letter or 3 letter language codes for your language code tag.

---
##### Notes:

This plugin will remove chapters from mp4 files.  Chapters are preserved in mkv files.
