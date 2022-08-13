import pathlib
from types import MethodType

# I developed on Python 3.10, but Mojave ships with Python 3.8
# which lacks some features.
if not hasattr(pathlib.PosixPath, "is_relative_to"):
    class PosixPathPlus(pathlib.PosixPath):
        def is_relative_to(self, other):
            a = str(self)
            b = str(other)
            return a.startswith(b)

    pathlib.PosixPath = PosixPathPlus
