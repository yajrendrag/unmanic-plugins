
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin adds custom metadata fields to mkv or mp4 container based files.
---

##### Documentation:

Specify metadata fields to add to the file.  For mkv containers specify a comma delimited list of
tagname:value pairs, e.g., mycustomtag1:value1, mycustomtag2:value2

In mkv files, the metadata will show up in the stream format tags section in the ffprobe data, e.g.,
{...
   ],
   "format": {
   ...
   {tags:
       ...
       "MYCUSTOMTAG1": "value1"
       "MYCUSTOMTAG2": "value2"
       ...
}

In mp4 files, the metadata will show up in the comments tag:
{...
   ],
   "format": {
   ...
   {tags:
       ...
       "comment": "mycustomtag1:value1", "mycustomtag2:value2"
       ...
}
--- 

### Config description:

#### <span style="color:blue">Custom Metadata</span>
Enter custom tags as tagname:value (no spaces), enter more than one pair by delimiting pairs with commas

:::note
:::
