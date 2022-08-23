"""\
Sync MacOS extended attributes through tools that do not support
them (like nextCloud or ownCloud).
"""

import sys, time, pathlib, re, threading, logging
from .logging import init_logging, debug, info, warning, error

from .configuration import ArgParseConfiguration, configuration
from .attr_storage import FilesystemAttributeStorage

from watchdog.observers.fsevents import ( BaseObserver, FSEventsObserver,
                                          FSEventsEmitter, )
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT
from watchdog.events import FileSystemEventHandler

nextcloud_tempfile_re = re.compile(r"\.(.*)\.~[a-f0-9]+$")

# We use the fsevents logger to debug() our event handling below.
# Event arrival and our processng of them may differ. 
fsevent_logger = logging.getLogger('fsevents')

class MyWatchdogEventHandler(FileSystemEventHandler):
    def __init__(self, attribute_storage:FilesystemAttributeStorage):
        self.storage = attribute_storage
        self.deletion_timers = {}

    def dispatch(self, event):
        try:
            FileSystemEventHandler.dispatch(self, event)
        except Exception as e:
            error(e, exc_info=True)            
        
    def on_modified(self, event):
        fsevent_logger.debug(f"MODIFICATION EVENT {event.src_path}")

        path = pathlib.Path(event.src_path)

        if not path.is_relative_to(configuration.storage_dir_path):            
            if not configuration.process_this(path):
                return
            
            self.storage.update_pickle_of(path)

    #def _process_watched_file_modification(self, path:pathlib.Path):
    #    debug(f"Processing watched file modified {path}")
        
    #    del self.modification_timers[path]    
    #    self.storage.update_pickle_of(path)

        
    def on_moved(self, event):
        fsevent_logger.debug(
            f"MOVE EVENT {event.src_path} -> {event.dest_path}")

        # NextCloud creates a tmpfile named .FILENAME.REVISION_IN_HEX.
        # In this case we copy metadata from the attribute store
        # to the file. 
        # The download/move does not create a modified event.
        # Chances are, the corresponding .asta file will be overwritten soon.
        # This is why we don’t.

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
        else:
            # A file not moved by nextCloud?
            # Check if the src_path is a watched file.
            #    If so, delete the pickle.
            # Check if the dest_path is (will be) a watched file.
            #    If so, pickle the attributes.
            src_path = pathlib.Path(event.src_path)
            dest_path = pathlib.Path(event.dest_path)
            
            if configuration.process_this(src_path):                
                self.storage.delete_pickle_for(src_path)

            if configuration.process_this(dest_path):
                self.storage.update_pickle_of(dest_path)

    def on_deleted(self, event):
        fsevent_logger.debug(f"DELETE EVENT {event.src_path}")

        # Events come in pretty much arbitrary order. Pages/Keynote/Numbers
        # sometimes delete a file on saving, create a tempfile and move
        # the tempfile to the previous location. If the delete event makes it
        # last in the queue, causing us to delete a pickle we still want to
        # hold on to. Thus we wait a little longer than
        # DEFAULT_OBSERVER_TIMEOUT and check if the watched files exists
        # (or has re-appeared) before deleting the pickle. 
        src_path = pathlib.Path(event.src_path)
        if configuration.process_this(src_path):
            if src_path in self.deletion_timers:
                self.deletion_timers[src_path].cancel()
            self.deletion_timers[src_path] = threading.Timer(
                DEFAULT_OBSERVER_TIMEOUT + .2,
                self._process_delete_event, args=[src_path,])
            self.deletion_timers[src_path].start()

    def _process_delete_event(self, src_path):
        del self.deletion_timers[src_path]
        
        if not src_path.exists():
            self.storage.delete_pickle_for(src_path)


class MyFSEventsEmitter(FSEventsEmitter):
    def _queue_modified_event(self, event, src_path, dirname):
        if event.is_xattr_mod:
            FSEventsEmitter._queue_modified_event(
                self, event, src_path, dirname)


class MyObserver(FSEventsObserver):
    def __init__(self, timeout=DEFAULT_OBSERVER_TIMEOUT):
        BaseObserver.__init__(
            self, emitter_class=MyFSEventsEmitter, timeout=timeout)
    
                    
def main():    
    parser = ArgParseConfiguration.make_argparser(__doc__)

    parser.add_argument("-d", "--debug",
                        dest="debug", action="store_true", default=False,
                        help="Commit debug information to log.")
    parser.add_argument("--info", dest="info",
                        action="store_true", default=False,
                        help="Log informative messages.")
    parser.add_argument("--log-events", dest="log_watchdog_events",
                        action="store_true", default=False,
                        help="Enable the watchdog module’s event logging.")
    parser.add_argument("-l", dest="logfile_path",
                        default=None,
                        type=pathlib.Path,
                        help="Where to write a logfiles (auto-rotated)")

    subparsers = parser.add_subparsers(help="command", dest="command")

    start_parser = subparsers.add_parser(
        "start", help="Start wathing the filesystem.")

    refresh_pickles = subparsers.add_parser(
        "refresh-pickles", help="Create a new pickle for each watched file.")

    refresh_files = subparsers.add_parser(
        "refresh-files",
        help="Write the extended attributes from each "
        "pickle found to the corresponding file.")

    show_pickles = subparsers.add_parser(
        "show-pickles", help="Print pickled extended attributes to stdout.")
    show_pickles.add_argument("res", nargs="+",
                              help="Filename regular expressions")
    
    args = parser.parse_args()

    ArgParseConfiguration(args).install()

    init_logging()
    
    if args.root_path is None:
        parser.error("error: the following arguments are required: --root/-r "
                     "or $ROOT_PATH must be set.")

    # Initialize the attr storage dir, start watching for changes.
    storage = FilesystemAttributeStorage()
    
    if args.command == "start":
        # Start watching the root dir.
        event_handler = MyWatchdogEventHandler(storage)
        observer = MyObserver()
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
    elif args.command == "show-pickles":
        import re
        from .logging import colored
        
        res = [ re.compile(regex, re.IGNORECASE) for regex in args.res ]
        
        for fileinfo in storage.matching_fileinfos(res):
            print(colored(str(fileinfo.relpath) + ":", "red"))
            attrs = fileinfo.attributes
            
            names = sorted(attrs.keys())
            for name in names:
                print(colored(name + ":" , "cyan"), str(attrs[name]))
            print()
    
if __name__ == '__main__':
    main()
