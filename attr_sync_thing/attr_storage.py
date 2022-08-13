import re, pathlib, pickle, uuid, time

from .configuration import configuration
from .modification_manager import modification_manager
from .file_info import FileInfo
from .logging import debug, info, warning, error

class PickleFile(object):
    def __init__(self, storage, filename:str, mtime:float, fi:FileInfo):
        self.storage = storage
        self.filename = filename
        self.mtime = mtime
        self.fi = fi

    @classmethod
    def from_pickle_file(cls, storage, filename):
        filepath = storage.pickle_file_path(filename)
        mtime = filepath.stat().st_mtime
        fi = pickle.load(filepath.open("rb"), fix_imports=False)

        return cls(storage, filename, mtime, fi)

    @classmethod
    def from_watched_file(cls, storage, filepath:pathlib.Path):
        """
        Create a FileInfo object from that file and pickle it in a
        new file.
        """
        pickle_file_name = storage.new_file_name()
        fi = FileInfo(filepath)

        self = cls(storage, pickle_file_name, 0, fi)
        self.update_pickle()        

        return self

    @property
    def pickle_file_path(self) -> pathlib.Path:
        return self.storage.pickle_file_path(self.filename)
    
    @property
    def watched_file_path(self):
        return self.fi.abspath
    
    def update_pickle(self):
        """
        • Reads the attributes from the watched file,
        • updates the FileInfo object
        • and stores it in its pickle file.
        """
        self.fi.read_from_file()

        modification_manager.register_modification(self.pickle_file_path)
        with self.pickle_file_path.open("wb") as fp:
            pickle.dump(self.fi, fp)
    
        self.mtime = self.pickle_file_path.stat().st_mtime

    def update_fileinfo(self):
        with self.pickle_file_path.open("rb") as fp:
            self.fi = pickle.load(fp)
        
            
class FilesystemAttributeStorage(object):
    def __init__(self):
        start_time = time.time()
        path = configuration.storage_dir_path.resolve()
        
        if not ".noindex" in path.name:
            if path.exists():
                raise IOError("Storage dir’s name must contain “.noindex”")
            
            path = pathlib.Path(path.parent, path.name + ".noindex")
            
        try:
            path.mkdir(exist_ok=True)
        except OSError:
            raise OSError("Can’t create storage dir. Parent dirs missing?")
            
        self.path = path

        ## Initialize fileinfo dict
        self._pickles = dict()

        for fp in self.path.iterdir():
            # This will skip files that don’t belong here.
            if fp.name.endswith(".asta"):
                pf = PickleFile.from_pickle_file(self, fp.name)
                relpath = pf.fi.relpath
                
                if not relpath in self._pickles:
                    self._pickles[relpath] = pf
                else:
                    # Duplicate pickle file. Deal with it by comparing mtimes.
                    mtime_existing = self._pickles[relpath].mtime
                    mtime_new = pf.mtime

                    if mtime_new > mtime_existing:
                        # The recently read pickle file is younger than
                        # the one previously read…
                        self._pickles[relpath].pickle_file_path.unlink()
                        del self._pickles[relpath]
                        
                        self._pickles[relpath] = pf
                    else:
                        # The recently read pickle file is older than
                        # the one previously read. This means our data is
                        # ok, we only delete the duplicate file.
                        fp.unlink()

        # Having arrived here, we have an up-to-date version of the metadata
        # in RAM. We’ll check on each of the files in the root directory.
        info("Attribute Storage read from", self.path,
             "with", len(self._pickles), "entries in ",
             f"{time.time()-start_time:.2f} seconds.")
        
    def update_pickle_of(self, watched_file_path:pathlib.Path):
        debug(f"update_pickle_of({watched_file_path})")
        relpath = configuration.relpath_of(watched_file_path)

        if relpath in self._pickles:
            self._pickles[relpath].update_pickle()
        else:
            self._pickles[relpath] = PickleFile.from_watched_file(
                self, watched_file_path)

    
    def delete_pickle_for(self, watched_file_path:pathlib.Path):
        debug(f"delete_pickle_for({watched_file_path})")
        watched_file_relpath = configuration.relpath_of(watched_file_path)
        if watched_file_relpath in self._pickles:
            # Try to remove the file from the filesystem…
            try:
                self._pickles[watched_file_relpath].pickle_file_path.unlink()
            except OSError:
                pass
            
            # and do remote it from our internal registry.
            del self._pickles[watched_file_relpath]
        
    def restore_from_pickle(self, watched_file_path:pathlib.Path):
        debug(f"restore_from_pickle({watched_file_path})")
        pickle = self._pickles.get(configuration.relpath_of(watched_file_path),
                                   None)
        if pickle is not None:
            pickle.fi.write_to_file()

    def process_updated_pickle(self, pickle_file_name:str):
        debug(f"process_updated_pickle({pickle_file_name})")
        pickle = PickleFile.from_pickle_file(self, pickle_file_name)
        self._pickles[pickle.fi.relpath] = pickle
        pickle.fi.write_to_file()
            
    def new_file_name(self) -> str:
        return str(uuid.uuid4()) + ".asta"

    def pickle_file_path(self, name:str) -> pathlib.Path:
        return pathlib.Path(self.path, name)

    def clear_all(self):
        self._pickles = {}

        for path in self.path.glob("*"):
            path.unlink()

    def rebuild_from_filebase(self):
        # Find all watched files.
        paths = configuration.root_path.rglob("*")
        paths = configuration.filter_ignored(paths)
        for fp in paths:
            relpath = configuration.relpath_of(fp)

            # Don’t update the pickle file if it’s
            # mtime is equal or younger than the watched file.
            pickle = self._pickles.get(relpath, None)
            if pickle is None or fp.stat().st_mtime <= pickle.mtime:
                self._pickles[relpath] = PickleFile.from_watched_file(self, fp)

    def refresh_watched_files(self):
        for pickle in self._pickles.values():
            try:
                pickle.fi.write_to_file()
            except IOError:
                pass

# UNIT TESTS ############################################################
if __name__ == "__main__":
    from .configuration import ArgParseConfiguration

    parser = ArgParseConfiguration.make_argparser("Run tests on this module.")
    
    parser.add_argument("command",
                        choices=["init", "pickle", "unpickle_to",
                                 "update_pickle"],
                        default="init")
    parser.add_argument("paths", type=pathlib.Path, nargs="+",
                        help="Some files to work on.")
    
    args = parser.parse_args()
    ArgParseConfiguration(args).install()

    storage = FilesystemAttributeStorage()

    if args.command == "init":
        # Just initialize the storage, don’t do anything.
        pass
    elif args.command == "pickle":
        for path in args.paths:
            storage.update_pickle_of(path.resolve())
    elif args.command == "unpickle_to":
        if len(args.paths) != 2:
            parser.error("Must have <source> <target> paths on cmd line. "
                         "Source must be a watched file.")

        source, target = args.paths

        relpath = configuration.relpath_of(source)
        pickle = storage._pickles[relpath]

        fake_fi = FileInfo(target, pickle.fi.attributes)
        fake_fi.write_to_file()
            
