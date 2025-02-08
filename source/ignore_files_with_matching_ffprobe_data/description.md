
Enter a jsonata expression of ffprobe fields to search for during library scans and new file event triggers.

Files with matching ffprobe field values will be ignored.

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

Find all streams matching codec_name field of h264".

  - **The ffprobe field to match against**
    ```
    $.streams[*].codecs_name
    ```
  - **Search strings**
    ```
    h264
    ```

Find all video streams matching codec_name field of "hevc" or "h264" if the video stream is greater than 1000px but smaller than 2000px (1080p).

  - **The ffprobe field to match against**
    ```
    [$.streams[codec_type="video" and (height > 1000) and (height < 2000)].codec_name]
    ```
  - **Search strings**
    ```
    hevc,h264
    ```

Find files with a duration greater than 5 minutes.

  - **The ffprobe field to match against**
    ```
    [$number($.streams[codec_type="Video"].duration) > 300 ? "true" : "false"]
    ```
  - **Search strings**
    ```
    true
    ```

:::warning
**Quotes**

The Python library used to parse the JSONata query does not support single quotes. Always use double quotes in your query as in the examples above.
