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
}

if __name__ == "__main__":
    setup(
        app=APP,
        options={"py2app": OPTIONS},
    )
