from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install ssi_fc_data into the current Python environment."
    )
    parser.add_argument(
        "package",
        nargs="?",
        default="ssi-fc-data",
        help="Path to ssi_fc_data tar.gz or package name resolvable by pip.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    package = args.package
    package_path = Path(package)

    if package_path.suffixes[-2:] == [".tar", ".gz"] and not package_path.exists():
        raise SystemExit(f"Khong tim thay file package: {package_path}")

    cmd = [sys.executable, "-m", "pip", "install", package]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
