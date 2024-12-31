]
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin operates only on MKV (Mastroska) files and splits the file into multiple constituent MKV files based 
on chapter markings or based on a configured time period.  The motivation for doing this is when a single MKV file
holdes multiple episodes of a show.  The file name is expected to indicate the presence of multiple episodes - if the
file name doesn't contain a string of Sxx[<sp><->]*Eyy[<sp>]*-[<sp>]*E*zz then the plugin will conclude the file does
not container multiple episodes to split.

In above string, Sxx and Eyy can be contiguous or can be separated by a space &/or a dash or a dash surrounded by spaces.
Eyy and Ezz can be separated by a dash, or a dash surrounded by spaces.  Moreover the final E in front of zz is optional.

That pattern needs to be somewhere in the basename of the video file for the plugin to conclude it has multiple episodes.

---

##### Documentation:

mkvtoolnix is used to do file splitting.  To learn more about this tool see:
- [MKVToolNix Documentation](https://mkvtoolnix.download/docs.html)

--- 

### Config description:

#### <span style="color:blue">Split Method</span>
Select Chapters, time, combo(chapters with time fallback; time is derived from duration divided by number of episodes), silence / black scene detection, tmdb lookup.
A tmdb API is required to use tmdb lookup - this is a free account currently.  Episode duration lookup is done and fine tuned with black scened detection.

#### <span style="color:blue">Season Dir</span>
The split files are put into the same folder as the multiepisode source unless Season Dir is checked.  if this option is selected a new folder for the split episodes
is put into the same directory as the multiepisode source.  you can choose from 4 patterns for the season folder:
- a folder named 'Series Title SxxEyy - resolution - quality'
- a folder named 'Season N'
- a folder named 'Series Title - Season N'
- a folder named 'Season N - Series Title'

#### <span style="color:blue">Keep Original</span>
Keep the original multiepisode source or not

#### <span style="color:blue">min_silence</span>
Used together with min_black to help mark chapters it is the minimum amount of silence required to discern a new chapter

#### <span style="color:blue">min_black</span>
Used together with min_silece to help mark chapters it is the minimum amount of time for a black screen required to discern a new chapter

For the split method of silence/black scene detection an overlapping scene of silence and black screen each configured with their minimum times is required to 
declare a new chapter (episode) has ocurrred.

These options are only visible if the silence / black scene detection split method is selected.

#### <span style="color:blue">tmdb_api_key</span>
your tmdb api key

#### <span style="color:blue">tmdb_api_read_access_token</span>
your tmdb api read access token

these options are only visible if the tmdb lookup split method is selected.
