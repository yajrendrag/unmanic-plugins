
---

##### Links:

- [Support](https://unmanic.app/discord)

---

##### Description:

This plugin delays a worker that is processing an incomplete file resulting from unmanic's file monitor
picking up a file before it's finished being moved into place.  In this case, the st version of this plugin
is designed to wait for the st tmp file to appear, then disappear before allowing processing to continue.
Moreover, the plugin will also monitor the original file for name changes performed by st.  the plugin 
will change the name of the file back to the original name, but saving the name given by st so that 
a post processor script can later change the final name of the file back to the name given by st
---

##### Documentation:

unmanic is monitoring create and closed events.
While unmanic's file monitoring doesn't use inotify per se, it is very similar.
See https://linux.die.net/man/1/inotifywait for more.
--- 

### Config description:

#### <span style="color:blue">notify_windo2</span>
The amount of time to monitor inotify events for a file.  this plugin continuously looks at this window of time for inotify events. The plugin simultaneously looks for zero inotify events in this window
of time as well as looking for the st tmp file name being available and then deleted and then finally looks for a st filename that differs from the original filename

#### <span style="color:blue">unmanic_ip_port</span>
Enter the host's ip address and port where unmanic is running.  This is used so that the plugin can communicate with the main application via unmanic's API.

:::note
This plugin should be the first plugin in the worker processing flow; otherwise it won't work.
:::
