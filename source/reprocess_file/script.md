#!/usr/bin/env bash
DATA=$(cat)  #passes the data object from the plugin into the script variable DATA as json
#### - Data objects passed to the script - see the examples below to parse them and assign them to script variables

        library_id                      - The library that the current task is associated with.
        task_id                         - Integer, unique identifier of the task.
        task_type                       - String, "local" or "remote".
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.
        start_time                      - Float, UNIX timestamp when the task began.
        finish_time                     - Float, UNIX timestamp when the task completed.
####

#### Parsing Examples
TASK_ID=$(echo "$DATA" | jq -r '.task_id') # uses jq to parse the 'task_id' json element of DATA and assigns it to the script variable TASK_ID

#ABSPATH=$(echo "$DATA" | jq -r '.source_data.abspath') # uses jq to parse the 'source_data.abspath' json element of DATA and assigns it to the script variable ABSPATH

#SUCCESS=$(echo "$DATA" | jq -r '.task_processing_success')

### Now use whatever fields you need
DB="/config/.unmanic/config/unmanic.db"  #unmanic database

### here's a sqlite command to find the task matching task_id and that have "Reconfiguring filter graph" or "hwaccel change" in the plugin command output
MATCH=$(sqlite3 "$DB" \
  "SELECT COUNT(*) FROM tasks
   WHERE id = ${TASK_ID}
   AND (log LIKE '%Reconfiguring filter graph%'
        OR log LIKE '%hwaccel changed%')")

### if MATCH is true (one of the above phrases is in the plugin command output) return 0, otherwise return 1.
[ "$MATCH" -gt 0 ] && exit 0 || exit 1

### in the reprocess_plugin script, 0 means that the reprocess plugin should continue and cause the file, abspath, to be reprocessed, whereas 1 means do not reprocess the file.
