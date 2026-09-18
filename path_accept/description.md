
Enter line-separated regex.


##### Examples:

```
^.*\(.*\).*\..*$
```
Accept files and directories containing parentheses '<span style="color:red">()</span>'

```
^.*\/ignore_folder\/.*$
```
Accept all contents of path containing '<span style="color:red">/ignore_folder/</span>'

```
^.*\/\..*\/.*$
```
Accept paths inside a hidden directory. Eg: <span style="color:red">/library/directory/.git/</span>

```
^.*\/\.[^/]*$
```
Accept hidden files. Eg: <span style="color:red">/library/directory/.fileinfo</span>

```
^.*2160p.*$
```
Accept paths containing '<span style="color:red">2160p</span>'

```
^.*\.inProgress$
```
Accept files suffixed with '<span style="color:red">.inProgress</span>'. Eg: <span style="color:red">/path/to/file.mp4.inProgress</span>
