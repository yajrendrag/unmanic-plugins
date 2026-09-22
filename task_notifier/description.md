
##### Description
Uses Apprise Notification (https://github.com/caronc/apprise) to send notifications on task success/failure.

- Configure plugin with location of apprise configuration file - defaults to /config/apprise_config.txt.
- Minimally, this should be a url corresponding to the underlying notification system(s) you want apprise to use.  See https://github.com/caronc/apprise/wiki/Config_text.
- More complex configuration is possible and yml files are also available if preferred - https://github.com/caronc/apprise/wiki/config_yaml.
- Multiple notification urls can be placed in /config/apprise_config.txt so a single execution of the plugin can send notifications to multiple underlying notification systems simultaneously
- Add task_notifier to your plugin stack and position accordingly in post processor marking task success/failure flow.
- upon task completion, the unmanic_notify post processor plugin will send notification with apprise.
- with version 0.0.3, optionally add `unmanic://` to your `/config/apprise_config.txt`.  Then supply a corresponding `/config/unmanic_notifier.sh` shell script - make it executable.  In it you want
to provide a custom script to do something with the video file based on the status (successful or unsuccessful).  Here is a start to extract the video file name and the status:

```
#!/bin/bash

status=$(printf %s "${1/$'\n'*/}")
vid_file=$(printf %s "${1/*$'\n'/}")

# write your own shell commands to further process the video file (vid_file) based on the status.
# success status message = "Unmanic successfully processed"
# unsuccessful status message = "Unmanic failed to process"
#
```

:::important
This plugin is installed using the init system and apprise is pip installed as part of the the plugin installation.  This means that at the time the plugin is installed, apprise is not necessarily installed.  To remedy this, just restart the unmanic container.  If, for some reason, this does not work for you, uninstall the plugin, get to a shell in your unmanic container (or host shell if you pip installed unmanic) and issue `python3 -m pip install apprise`.  After the apprise module is installed, simply install the plugin.
:::
