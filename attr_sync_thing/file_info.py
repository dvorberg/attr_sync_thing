import pathlib
import xattr

from .logging import debug, info, warning, error
from .configuration import configuration
from .modification_manager import modification_manager

class FileInfo:
    """
    Container for the relative path and relevant attributes of a
    filesystem object.
    """
    def __init__(self, path:pathlib.Path, attributes = {}):
        self._relpath = configuration.relpath_of(path)
        self._attributes = attributes.copy()
        
    @classmethod
    def from_file(cls, path):
        # If I only want to preserve certain attributes, they need to be
        # filtered here.
        self = cls(path)
        self.read_from_file()
        return self

    @property
    def relpath(self) -> str:
        return self._relpath

    @property
    def abspath(self) -> pathlib.Path:
        return configuration.abspath_of(self._relpath)

    @property
    def attributes(self) -> dict:
        """
        Returns a copy of our attributes. This class does not modify
        single attributes.
        """
        return self._attributes.copy()    

    @property
    def _accessor(self) -> xattr.xattr:
        """
        The accessor is a dict-like object mapping xattrs names to their
        value. Performs filesystem access on dict access.
        """
        return xattr.xattr(str(self.abspath))

    def read_from_file(self):
        self._attributes = dict(self._accessor.iteritems())        
    
    def write_to_file(self):
        try:
            a = self._accessor
        except OSError:
            pass
        else:        
            modification_manager.register_modification(self.abspath)
        
            a.clear()
            for name, value in self._attributes.items():
                if name in configuration.attributes_to_copy:
                    a[name] = value

        
# UNIT TESTS ############################################################
if __name__ == "__main__":
    from .configuration import ArgParseConfiguration
    
    parser = ArgParseConfiguration.make_argparser("Run tests on this module.")
    
    parser.add_argument("command", choices=["list", "copy", "clear",])
    parser.add_argument("paths", type=pathlib.Path, nargs="+",
                        help="Some files to work on.")
    
    args = parser.parse_args()
    ArgParseConfiguration(args).install()

    
    if args.command == "list":
        for path in args.paths:
            fi = FileInfo.from_file(path)
            print(fi.relpath, fi._attributes)            
    elif args.command == "copy":
        if len(args.paths) != 2:
            parser.error("copy command needs to params, copying attrs from "
                         "to another.")
        a = args.paths[0]
        b = args.paths[1]

        # Read the xattrs using from_file() on file a …
        fi_a = FileInfo.from_file(a)

        # …create an FileInfo object for file b with the attributes from file a
        fi_b = FileInfo(b, fi_a.attributes)

        # … and write those attributes to disk. 
        fi_b.write_to_file()
    elif args.command == "clear":
        for path in args.paths:
            abspath = str(path.resolve())
            accessor = xattr.xattr(abspath)
            accessor.clear()
                                                 
