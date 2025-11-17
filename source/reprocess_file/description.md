
##### Links:

- [Support](https://unmanic.app/discord)

---


##### Description
This plugin will add the original source file back to task queue for processing by a library selected in the plugin's configuration.  You can 
elect to always reprocess files, or elect to process files only on task success or only on task failure.  The intention of this plugin is that
you reprocess the file with another library stack to process it with other plugins after the file has completed processing with the current library.

The path of the file for reprocessing is identical to the original file, so the library that is reprocessing the file should be defined over the same
set of media folders as the original library.

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

:::Note
This plugin is a post processing plugin so is only executed by a main instance of unmanic.  If you are using linked instances it is not needed to put this file
on a linked instance - the main instance will determine task success or failure will requeue the file accordingly and normal task processing will determine which
unmanic instance will ultimately process the file.
:::
