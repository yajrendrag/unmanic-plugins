The plugin allows you to run mkvpropedit on a file.

There are some pre-build arguments that you can turn on with a checkbox like:

- Add Track Statistics Tags: This adds `--add-track-statistics-tags` to your arguments
- Remove Title Tag: This adds `-d title` to your arguments
- Add Encode Source To Global Tags: This takes the original file name passed into unmanic, and adds it as a global tag to the mkv file

Anything not built in can be added to the Other Arguments section.

---

#### Important Note

You must make sure that mkvpropedit is installed and available in the PATH so that this plugin can use it. To do that you can do something like this:

1. reate a file inside the container `/config/startup.sh`
2. Inside this file append the following contents:

```sh
#!/bin/bash

/usr/bin/apt-get update ;
/usr/bin/apt-get install -y mkvtoolnix
```
