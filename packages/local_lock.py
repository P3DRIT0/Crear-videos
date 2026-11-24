"""Exclusión local entre procesos en Linux y Windows."""
from contextlib import contextmanager
import os


@contextmanager
def exclusive_file(path):
    with path.open("a+b") as handle:
        if os.name=="nt":
            import msvcrt
            if handle.tell()==0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield handle
