
##### Description

This plugin arranges the streams in a video file, keeping the source container, to be in the following order:
- video
- audio
- subtitles
- data
- attachments

Note that some stream types may not be compatible or even able to be copied to the existing container type.  If you get an error about incompatible streams, you may need to 
couple the use of this plugin with other plugins that remove subtitles, data, or attachment streams before this plugin executes (place them before this plugin
in your worker flow).

In addition, you can sort the audio streams by a combination of number of channels and languages.  You can choose to sort by channels first and then language
or by language first and then channels.  You specifiy a list of languages to sort by in the order in which you wish them to appear in the output.  Any streams
with languages not matching your list of languages will be place after the langauges you list.  Channel sort will be based on the actual audio streams in the file;
you just specify whether the sort is ascending or descending.


##### Configuration Options
- audio primary sort key is either channels or languages - specify it in the dropdown.
- channels sort direction is either ascending (2, 5.1, 7.1), or descending (5.1, 2).
- Enter a comma delimited list of audio language codes to sort by.

Three letter language codes should be used where applicable.


