
**<span style="color:#56adda">0.1.0</span>**
- added new capability to run a user supplied script to evaluate whether to reprocess the file 
- only used when plugin is running in a mode to reprocess based on success or failure - not on all files
  - specify the location of a diagnostic script - option only visible when reprocess_based_on_task_status is true.  e.g., /config/colorspace.sh
  - plugin passes the entire data object to the script for use as script variables
  - see script.md for further documentation

**<span style="color:#56adda">0.0.3</span>**
- use threading to add the task back to the task list
- necessary in the case where the file name remains identical to the filename in the original task - so old task is detected as deleted

**<span style="color:#56adda">0.0.2</span>**
- updated description.md to explain the additional options

**<span style="color:#56adda">0.0.1</span>**
- Initial version
