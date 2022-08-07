import os, argparse, pathlib, fnmatch

class ConfigurationWrapper(object):
    def __init__(self):
        self._real = None
    
    def install(self, configuration):
        self._real = configuration
        return self

    def __getattr__(self, name):
        return getattr(self._real, name)

configuration = ConfigurationWrapper()

class Configuration(object):
    def __init__(self):
        pass

    def install(self):
        return configuration.install(self)

    def process_this(self, path:pathlib.Path):
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return False

        rpath = path.resolve()
            
        if rpath.is_relative_to(self.storage_dir_path):
            return False

        if path.is_symlink():
            return False

        if not rpath.is_relative_to(self.root_path):
            return False
        
        return True
        
    def filter_ignored(self, filepaths):
        return filter(self.process_this, filepaths)
        
    @property
    def storage_dir_path(self):
        assert not self.storage_dir_name.is_absolute(), \
            ValueError("Storage dir name must be relative path to root dir.")
        return pathlib.Path(self.root_path, self.storage_dir_name)
        
    def relpath_of(self, abspath:pathlib.Path) -> str:
        return str(abspath.resolve().relative_to(self.root_path))

    def abspath_of(self, relpath:str) -> pathlib.Path:
        return pathlib.Path(self.root_path, relpath).resolve()
            
    
class DefaultConfiguration(Configuration):
    pass
    
class ArgParseConfiguration(Configuration):

    # https://help.dropbox.com/de-de/installs-integrations/sync-uploads/extended-attributes
    attributes_to_copy = set((
        "com.apple.ResourceFork",
        "com.apple.FinderInfo",
        "com.apple.metadata:_kMDItemUserTags",
        "com.apple.metadata:kMDItemFinderComment", # Doesn’t seem to work :-( 
        "com.apple.metadata:kMDItemOMUserTagTime",
        "com.apple.metadata:kMDItemOMUserTags",
        "com.apple.metadata:kMDItemStarRating",))
    
    def __init__(self, args):
        self._args = args

    def __getattr__(self, name):
        return getattr(self._args, name)

    @classmethod
    def make_argparser(cls, description):
        parser = argparse.ArgumentParser(description=description)

        parser.add_argument("--root", "-r", dest="root_path",
                            default=os.getenv("ROOT_PATH", None),
                            type=pathlib.Path)
        parser.add_argument("--storage", "-s", dest="storage_dir_name", 
                            default=os.getenv("STORAGE_DIR_NAME",
                                              "Attribute_Storage.noindex"),
                            type=pathlib.Path)
        parser.add_argument("--ignore", "-i", dest="ignore_patterns",
                            default=[".DS_Store", "*~", ".*", "#*#"],
                            nargs="*")
        
        return parser

#class FileBasedConfiguration(Configuration):
#    # Your code goes here.
#    pass
    
