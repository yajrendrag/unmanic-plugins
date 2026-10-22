
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin delays a worker that is processing an incomplete file resulting from unmanic's file monitor
picking up a file before it's finished being moved into place.  The best way to handle this is to use the
limit library search by file extension plugin and configure it with a list of legitimate file extensions
corresponding to the type of file being processed in the library.  If the file being moved into place isn't
getting a temporary suffix, e.g., .part, however, then this doesn't work.  This plugin is intended to work
around that issue.
---

##### Documentation:

unmanic is monitoring create and closed events.
While unmanic's file monitoring doesn't use inotify per se, it is very similar.
See https://linux.die.net/man/1/inotifywait for more.
--- 

### Config description:

#### <span style="color:blue">Custom Metadata</span>
there are 2 configuration parameters:
-notify_window - the amount of time to monitor inotify events for a file.  this plugin continuously looks at this window of time for inotify events. only after seeing zero inotify events in this window
of time will the plugin move on to the next test which is ensuring the file size is remaining constant.

-size_window - the frequency with which the plugin should check the size of the file.  the plugin will break out of this mode once the file size is the same at the beginning and end of the this window.

both parameters should be set in whole seconds.

:::note
This plugin should be the first plugin in the worker processing flow; otherwise it won't work.
:::
