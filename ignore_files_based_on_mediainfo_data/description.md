
Enter a jsonata expression of mediainfo fields to search for during library scans and new file event triggers.

Files with matching Mediainfo field values will be ignored.

---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Documentation:

For information on formulating JSONata queries:
- [JSONata Documentation](https://docs.jsonata.org/overview.html)
- [JSONata Exerciser Tool](https://try.jsonata.org/pdNmg6BId)

---

##### Additional Information:

Try the **JSONata Exerciser Tool** listed in the Documentation above.

###### Examples:

Find all streams matching codec_name field of AVC".

  - **The Mediainfo field to match against**
    ```
    $.streams[*].codecs_video
    ```
  - **Search strings**
    ```
    AVC
    ```

Find all video streams matching codec_name field of "hevc" or "h264" if the video stream is greater than 1000px but smaller than 2000px (1080p).

  - **The Mediainfo field to match against**
    ```
    [$.streams[track_type="Video" and (height > 1000) and (height < 2000)].format]
    ```
  - **Search strings**
    ```
    HEVC,AVC
    ```

Find files with a duration greater than 5 minutes.

  - **The Mediainfo field to match against**
    ```
    [$.streams[track_type="Video"].duration > 300 ? "true" : "false"]
    ```
  - **Search strings**
    ```
    true
    ```

:::warning
**Quotes**

The Python library used to parse the JSONata query does not support single quotes. Always use double quotes in your query as in the examples above.

The mediainfo python library (pymediainfo) uses somewhat different syntax for some fields than the shell based version of the mediainfo tool - you may need to use a python interpretor to
inspect streams for the correct syntax for some fields.  See https://pymediainfo.readthedocs.io/en/stable/ 
:::
