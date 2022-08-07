"""\
<put description here>
"""

import sys, time, pathlib, re, threading

from .logging import debug, log
from .configuration import ArgParseConfiguration, configuration
from .attr_storage import FilesystemAttributeStorage
from .modification_manager import modification_manager

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

nextcloud_tempfile_re = re.compile(r"\.(.*)\.~[a-f0-9]+$")


class MyWatchdogEventHandler(FileSystemEventHandler):
    def __init__(self, attribute_storage:FilesystemAttributeStorage):
        self.storage = attribute_storage
        self.modification_timers = {}
        
    def on_modified(self, event):
        path = pathlib.Path(event.src_path)
        if modification_manager.did_we_modify(path):
            return

        if path ==  configuration.storage_dir_path:
            return
        
        if path.is_relative_to(configuration.storage_dir_path):
            
            debug("Pickle file updated", path)

            # now = time.time()
            # relpath = configuration.relpath_of(path)
            # pickle = self.storage._pickles.get(relpath, None)

            # # If the pickle is newer than the file, update the file’s
            # # xattrs from the pickle.
            # if path.stat().st_mtime <= pickle.mtime:
            
        else:
            if not configuration.process_this(path):
                return
            
            # Modifications sometimes come in bursts (Pages, Numbers, …).
            # We wait 1/2sec before acting on them.
            if path in self.modification_timers:
                self.modification_timers[path].cancel()
                
            self.modification_timers[path] = threading.Timer(
                0.5, self._process_watched_file_modification, args=[path,])
            self.modification_timers[path].start()

    def _process_watched_file_modification(self, path:pathlib.Path):
        debug("Processing watched file modified", path)
        
        del self.modification_timers[path]    
        self.storage.update_pickle_of(path)

        
    def on_moved(self, event):
        debug("MOVE", event.src_path, event.dest_path)

        # NextCloud creates a tmpfile named .FILENAME.REVISION_IN_HEX.
        # In this case we copy metadata from the attribute store
        # to the file. 
        # The download/move does not create a modified event.
        # Chances are, the corresponding .asta file will be overwritten soon.
        # This is why we don’t

        src_name = event.src_path.split("/")[-1]
        dest_name = event.dest_path.split("/")[-1]
        
        match = nextcloud_tempfile_re.match(src_name)
        if match is not None:
            filename = match.group(1)
            if filename == dest_name:
                path = pathlib.Path(event.dest_path)

                def try_twice(f):
                    try:
                        f()
                    except IOError:
                        timer = threading.Timer(0.75, f)
                        timer.start()
                
                if path.is_relative_to(configuration.storage_dir_path):
                    def attempt_process_updated_pickle():
                        self.storage.process_updated_pickle(path.name)
                    try_twice(attempt_process_updated_pickle)
                else:
                    def attempt_restore_from_pickle():
                        self.storage.restore_from_pickle(path)
                    try_twice(attempt_restore_from_pickle)
def main():
    parser = ArgParseConfiguration.make_argparser(__doc__)

    parser.add_argument("command", choices=["start",
                                            "refresh-pickles",
                                            "refresh-files"])
    
    args = parser.parse_args()
    ArgParseConfiguration(args).install()

    # Initialize the attr storage dir, start watching for changes.
    storage = FilesystemAttributeStorage()

    

    if args.command == "start":
        # Start watching the root dir.
        event_handler = MyWatchdogEventHandler(storage)
        observer = Observer()
        observer.schedule(event_handler, configuration.root_path,
                          recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()
    elif args.command == "refresh-pickles":
        # Clear the attribute storage.
        storage.clear_all()
        storage.rebuild_from_filebase()
    elif args.command == "refresh-files":
        storage.refresh_watched_files()
    
if __name__ == '__main__':
    main()