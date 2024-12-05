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
Select Chapters or Time or Combo - Combo tries to use chapter marks but if they are missing it will fall back to a time interval.

#### <span style="color:blue">Time Period</span>
If Time or Combo is specified as the split method, configure an amount of time per split (episode).  Whole minutes only

