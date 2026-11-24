"""Arranque auditado de ComfyUI con sockets Python limitados a loopback."""
import argparse
import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from packages.network_policy import install


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    args,remaining=parser.parse_known_args()
    root=args.root.resolve()
    if not (root/"main.py").is_file():
        raise ValueError("Falta ComfyUI main.py")
    install()
    os.chdir(root)
    sys.path.insert(0,str(root))
    sys.argv=[str(root/"main.py"),*remaining]
    runpy.run_path(str(root/"main.py"),run_name="__main__")


if __name__=="__main__":
    main()
