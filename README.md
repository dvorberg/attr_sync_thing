Sync MacOS extended attributes through tools that do not support them (like nextCloud or ownCloud).

This script will create a pickle file for each file in your synced filter tree. These files get synced by the cloud system’s desktop client. The script will watch for changes in the file tree and sync pickles to metadata and metadata to pickles on each of your computers. It is designed to be run as a normal user’s service through `launchd`. 

Extended attribute (Finder Metadata) sync is missing from ownCloud and nextCloud. I checked the source code of the (otherwise excellent) MacOS desktop clients, but my C++ skills aren’t good enough to implement it. My Python skills will have to do.

## Installation

I am afraid some system administration skills (changing plain-text files, running commands in the terminal) are required. Rudementary Python skills won’t hurt. Neither will knowing a little bit about launchd. 

This installation guide assumes MacOS 12.5 (because that’s what I got here). We will be using the Python 3.8 installation that shipes with the OS (or with Xcode? I honestly don’t know) and install to`~/Library/Python`. 

If you run your own version of Python, you know what a virtualenv ist and how to use it – cool! 

(1) We start by **installing the Python module and its dependencies**:

```shell
/usr/bin/pip3 install attr-sync-thing
```

Following this command, there should be a script available at `~/Library/Python/3.8/bin/attr_sync_thing` callable like this:

```shell
you@yourmac~$ ~/Library/Python/3.8/bin/attr_sync_thing 
usage: attr_sync_thing [-h] [--root ROOT_PATH] [--storage STORAGE_DIR_NAME]
                       [--ignore [IGNORE_PATTERNS [IGNORE_PATTERNS ...]]] [-d]
                       {start,refresh-pickles,refresh-files}
attr_sync_thing: error: the following arguments are required: command
```

(2a) **On the first Mac you install on:** 

We are ready to create our initial set of pickle files:

```shell
you@yourmac$ ~/Library/Python/3.8/bin/attr_sync_thing -r ~/Nextcloud refresh-pickles
```

This will create `~/Nextcloud/Attribute_Storage.noindex` with a bunch of `.asta` files in it. You may (optionally) hide this file from the `Finder` by issuing:

```shell
you@yourmac$ chflags hidden ~/Nextcloud/Attribute_Storage.noindex/
```

This step you’ll need to perform on all Macs you want it to be hidden on. *Cloud does not copy the `hidden` flag for us. 

(2b) **On all other Macs:**

On the other Macs we assume that the nextCloud or ownCloud desktop client has done its work and downloaded all those `.asta ` files from the cloud. On my system syncing 28,000 files took some patience and several friendly restarts of the nextCloud app to achieve this. 

Anyway, here we issue:

```shell
you@yourmac$ ~/Library/Python/3.8/bin/attr_sync_thing -r ~/Nextcloud refresh-files
```

This will copy the metadata from the pickle files to the watched files. 

(2c) **Optional: Testing**

You can run the script as-is. 

```shell
you@yourmac$ ~/Library/Python/3.8/bin/attr_sync_thing -r ~/Nextcloud -d start
```

The `-d`, “debug”, command line parameter will make it report the `watchdog` events is processing. Logging could be more informative, but I got it to work this way, so my motivation is limited.

(3) **Creating a LaunchAgent plist**

Create a file named something like `~/Library/LaunchAgents/de.tux4web.attr-sync-thing.plist` with the following contents:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
	<dict>
		<key>Label</key>
		<string>de.tux4web.attr-sync-thing</string>
        
		<key>Program</key>
		<string>/Users/you/Library/Python/3.8/bin/attr_sync_thing</string>

        <key>ProgramArguments</key>
        <array>
            <string>/Users/you/Library/Python/3.8/bin/attr_sync_thing</string>

            <string>-r</string>
            <string>/Users/you/Nextcloud</string>

            <string>--debug</string>

            <string>-l</string>
            <string>/Users/you/Library/Logs/attr_sync_thing.log</string>

            <string>start</string>
        </array>

        <key>KeepAlive</key>
        <true/>

        <!-- stderr output might be useful for users to capture
             if something doesn’t work as expected.
             Uncought Python Exceptions will end up here. -->
        <!--key>StandardErrorPath</key>
        <string>/Users/you/Library/Logs/attr_sync_thing.error.log</string-->

        <key>StartInterval</key>
        <integer>20</integer>

        <key>WorkingDirectory</key>
        <string>/Users/you</string>
	</dict>
</plist>
```

Dont forget to **change “you” to your login**!

My comments on logging might be usefull to those, who want to develop the script further. Capturing stdout doesn’t seem to work, though. 

(3) **Loading it into `launchcrl`**

This will do the trick:

```shell
you@yourmac:~$ launchctl load ~/Library/LaunchAgents/de.tux4web.attr-sync-thing.plist
```

Verify that the launch agent is loaded:

```shell
you@yourmac:~$ launchctl list | grep attr-sync-thing
51946	0	de.tux4web.attr-sync-thing
```

You may also verify that the Python Process is running by:

```shell
you@yourmac:~$ ps -ef|grep Python
 1001 51972 51946   0  9:12PM ??         0:04.30 /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.8/Resources/Python.app/Contents/MacOS/Python -m attr_sync_thing -d -r /Users/you/Nextcloud/ start
 1001 51978 45668   0  9:12PM ttys001    0:00.00 grep Python
```

This should be it. It should still be there after a reboot and hybernation. 

To get rid of if run:

```shell
you@yourmac:~$ launchctl unload ~/Library/LaunchAgents/de.tux4web.attr-sync-thing.plist
```

This will kill the process and not restart it until you `load` the plist again. See https://www.launchd.info for documentation on that thing. 
