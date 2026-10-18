"""Create a small source archive without build caches or bundled runtimes."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


root = Path(__file__).resolve().parent
output = root / "dist" / "Qingying-Source-1.0.0.zip"
output.parent.mkdir(parents=True, exist_ok=True)
files = [
    "src/core.py", "src/main.py", "make_icon.py", "package_source.py",
    "build.ps1", "installer.nsi", "requirements.txt", "README.md",
    ".gitignore",
    "USER_GUIDE.txt", "THIRD_PARTY.txt", "assets/icon.ico",
    "assets/icon.png", "assets/NotoSansSC.ttf", "assets/OFL.txt",
]
files += [str(path.relative_to(root)) for path in (root / "licenses").iterdir() if path.is_file()]
with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=6) as archive:
    for relative in files:
        archive.write(root / relative, relative)
print(output)
