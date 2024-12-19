
To find your Plex token, follow the instructions found here: 
- https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

Alternatively, navigate to the Plex data folder on your Plex server and open the Preferences.xml file and look for the value of "PlexOnlineToken".

These two approaches will likely yield different tokens, but both should work.

#### Configuration

- Enter the url for your Plex Server using your local IP address (ie, not the plex.tv cloud address)
- Enter the Plex token you found as per above
- Enter as a single string, the a mapping that shows your host media path relative to your unmanic library media path.  The mapping should only go include where the paths are
  different, e.g., /media:/library.  This means that Plex sees your media at the path /media and unmanic sees it at /library.  Below these paths the paths should be identical.
  You should have a unique mapping for each library in which this plugin is deployed, e.g., TVShows, Movies, etc.
- enter True or False for whether this plugin should run an update if the task for the file failed.

:::note
If you are not running Unmanic in docker, then for the above library mapping, just enter the mapping to be identical on both sides of the colon, e.g., /media/TVShows:/media/TVShows
:::
