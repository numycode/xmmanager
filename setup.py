from setuptools import setup

APP = ["main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": True,
    "plist": {
        "CFBundleName": "XMManager",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleIdentifier": "dev.numycode.xmmanager",
        "LSUIElement": True,
    },
    "packages": ["rumps"],
    "includes": ["Cocoa"],
    "excludes": ["tkinter", "test"],
}

if __name__ == "__main__":
    setup(
        app=APP,
        data_files=DATA_FILES,
        options={"py2app": OPTIONS},
    )
