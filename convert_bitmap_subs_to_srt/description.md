
##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description
This plugin finds bitmap (image based) subtitle streams in video files and converts them to SRT text files using Tesseract OCR.
The SRT files are named after the output video file plus the stream's language and title tags, e.g. `movie.eng.srt`
or `movie.eng.Forced-English-Subtitles.srt`. The plugin does not change the video file itself.

The SRT files are written next to the final output file once Unmanic has finished moving it. By default that is the
original file's location. If a file movement plugin such as Mover v2 sends the output somewhere else, the SRT files go
there too. If there are several output files, each one gets a copy of the SRT files. If the task fails, no SRT files
are written.

Converted files are recorded in Unmanic's file metadata database, so they are not queued again by later library scans.
The record is kept on both the source file and the output file.

Supported subtitle codecs:
- `hdmv_pgs_subtitle` - Blu-ray PGS
- `dvd_subtitle` - DVD / VobSub

Tesseract and its language packs are installed by the plugin's init.d script when the container starts.

##### How it works
1. **The subtitles are decoded into black-and-white images**, keeping only the text fill and dropping outlines and shadows.
   - PGS streams are copied out to a `.sup` file with ffmpeg, which the plugin then reads.
   - DVD streams are read packet by packet with ffprobe and decoded by the plugin.
2. **Tesseract reads the images and the plugin writes the SRT file.**
   - Images go to Tesseract in batches of 10 to 100 per process (sized so progress updates often), with up to 4
     processes at once.
   - Repeated display updates showing the same text (PGS fades) are merged into one subtitle.
   - A subtitle with no end time ends when the next one starts, or after 10 seconds at most.
   - Each stream is converted in its own helper process. The dashboard shows its progress and the time remaining,
     and pausing or terminating the worker pauses or stops the conversion, including the Tesseract processes.
3. **The SRT files are copied to their destination.** Steps 1 and 2 run in the worker and keep the SRT files in the
   task's cache folder. After the postprocessor has moved the output file, the plugin copies the SRT files next to it.

---

#### Config description:

##### <span style="color:DeepSkyBlue">"Subtitle languages to extract"</span>
A comma-separated list of the stream language tags to convert, e.g. `eng,fre,spa`. Only subtitle streams whose language tag is
in the list are converted. Leave empty to convert all bitmap subtitle streams.

##### <span style="color:DeepSkyBlue">"Tesseract OCR language"</span>
The language Tesseract uses to read the text. Defaults to `auto`.
- `auto` picks the language from each subtitle stream's language tag, including the older codes often found in MKV files
  (`fre`→`fra`, `ger`→`deu`, `dut`→`nld`). Streams with no usable language tag fall back to `eng`.
- Or enter a Tesseract language code, e.g. `eng`, `deu`, `fra` or `spa`. Several languages can be combined with `+`, e.g. `eng+fra`.

Installed languages: `eng`, `deu`, `fra`, `spa`, `ita`, `por`, `nld`, `pol`, `rus`, `jpn`, `chi_sim`, `chi_tra`, `kor`, `ara`.
If a requested language is not installed, a warning is logged and `eng` is used instead.
