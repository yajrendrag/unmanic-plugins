
##### Links:

- [Support](https://unmanic.app/discord)

---


##### Description
This plugin will add the original source file back to task queue for processing by a library selected in the plugin's configuration.  You can 
elect to always reprocess files, or elect to process files only on task success or only on task failure.  The intention of this plugin is that
you reprocess the file with another library stack to process it with other plugins after the file has completed processing with the current library.

Unless you use options below to change the suffix &/or perform a path translation, the path of the file for reprocessing is identical to the original file,
so the library that is reprocessing the file should be defined over the same set of media folders as the original library.

---

### Config description:

#### <span style="color:blue">"target_library"</span>
Select the library that will be used to reprocess the file.  This library needs to exist - the plugin does not create a new library.

#### <span style="color:blue">"reprocess_based_on_task_status"</span>
Check or uncheck this option.  If checked, you will see the option below and you will configure the plugin to either reprocess the file if the task
was successful or unsuccessful.  If this option is unchecked, it means always reprocess the file regardless of task processing success or failure.

#### <span style="color:blue">"status_that_adds_file_to_queue"</span>
Select "Success" or "Failed".  A selection of "Success" means that the file will be reprocessed ONLY if task processing was successful.  A selection of "Failed"
means that the file will be reprocessed ONLY if task processing was unsuccessful.

#### <span style="color:blue">"change_suffix"</span>
If you enable the change suffix option, you will also see the new_suffix option below.  this option tells the plugin that you want to process a file that has a
different suffix than the original file.  this is useful for example if you originally process a video file, but also have a subtitle or other file that has the identical
name except for the suffix and wish to process the file with the other suffix.

#### <span style="color:blue">"new_suffix"</span>
This is the suffix for the file that you want to process with your other library - the filename should match the original file name in all other respects other than the suffix.

#### <span style="color:blue">"modify_path"</span>
Enabling this option allows you to modify the path of the file you want to process.  So if you just processed a file and want to process another file with the same name except that
it has a leading path that is different than the original file, you can perform a path map translation to calculate the name of the file to be processed by your other library.  Specify the 
path map translation below.

#### <span style="color:blue">"path_map"</span>
The path map must be of the form /old-leading/path/components:/new-leading/path/components.  The components do not have to be the same length, but after these old and new components,
the remainder of the path in both locations must have the same components. This can be combined with the change_suffix option so that you can, for example, process the original file of 
"/path/to/original/video_file.mp4" and use this plugin to add a task to another library for a file name of "/some/new/path/to/original/video_file.srt".  The path map you would use in this
instance would be /path:/some/new/path.

:::Note
This plugin is a post processing plugin so is only executed by a main instance of unmanic.  If you are using linked instances it is not needed to put this file
on a linked instance - the main instance will determine task success or failure will requeue the file accordingly and normal task processing will determine which
unmanic instance will ultimately process the file.
:::
