
Uses Apprise Notification (https://github.com/caronc/apprise) to send notifications on task success/failure.

- Configure plugin with location of apprise configuration file - defaults to /config/apprise_config.txt.
- Minmally, this should be a url corresponding to the underlying notification system(s) you want apprise to use.  See https://github.com/caronc/apprise/wiki/Config_text.
- More complex configuration is possible and yml files are also available if preferred - https://github.com/caronc/apprise/wiki/config_yaml.
- Multiple notification urls can be placed in /config/apprise_config.txt so a single execution of the plugin can send notifications to multiple underlying notification systems simultaneously
- Add task_notifier to your plugin stack and position accordingly in post processor marking task success/failure flow.
- upon task completion, the unmanic_notify post processor plugin will send notification with apprise.
