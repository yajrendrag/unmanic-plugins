]
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin operates only on MKV (Mastroska) files and splits the file into multiple constituent MKV files based 
on chapter markings or based on a configured time period.  The motivation for doing this is when a single MKV file
holdes multiple episodes of a show.  The file name is expected to indicate the presence of multiple episodes

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

