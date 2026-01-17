
**<span style="color:#56adda">0.0.15</span>**
- add option for setting case for appended or replaced pathname elements
- edit relevant .unmanic file and replace old name with new name so file is not reprocessed

**<span style="color:#56adda">0.0.14</span>**
- add option to add codec name in replace mode even when source file has no codec name in the file name

**<span style="color:#56adda">0.0.13</span>**
- add check for audio metadata presence in ffprobe data

**<span style="color:#56adda">0.0.12</span>**
- fix typo in elif: clause

**<span style="color:#56adda">0.0.11</span>**
- fix error in channels test - should be int not str

**<span style="color:#56adda">0.0.10</span>**
- fix error in replace function variable - vrezh->vrez_height

**<span style="color:#56adda">0.0.9</span>**
- add option to use non-standard resolution based on height only and field_order value
- cleaned up logger output and made consistent between replace and append modes

**<span style="color:#56adda">0.0.8</span>**
- change reference to file's parsed resolution to rez from resolution

**<span style="color:#56adda">0.0.7</span>**
- fix typo in variable name

**<span style="color:#56adda">0.0.6</span>**
- fix replace function resolution
- provide for destination file change due to a remux or mover operation

**<span style="color:#56adda">0.0.5</span>**
- change video resolution format from WxH to Common Name, e.g., 1080p

**<span style="color:#56adda">0.0.4</span>**
- fix audio replacement function - variables were reversed
- fix rename relaed function to explicitly exclude video suffix file

**<span style="color:#56adda">0.0.3</span>**
- added renaming of related files (same basename with other extensions, .e.g., .srt, .nfo, etc)

**<span style="color:#56adda">0.0.2</span>**
- added 2nd option of replacing sections of filename with resuls from transcode
- this is an option instead of simply appending with ffprobe fields
- governed by 1st checkbox option

**<span style="color:#56adda">0.0.1</span>**
- Initial version
