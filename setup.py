import sys

from setuptools import Distribution, setup

APP = ['main.py']
DATA_FILES = ['']
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
    },
    'packages': ['rumps'],
    'includes': ['Cocoa'],
}

class Py2AppDistribution(Distribution):
    """Clear install_requires for py2app to avoid DistutilsOptionError."""
    def finalize_options(self):
        super().finalize_options()
        if "py2app" in sys.argv:
            self.install_requires = []


setup(
    app=APP,
    options={'py2app': OPTIONS},
    distclass=Py2AppDistribution,
    setup_requires=['py2app'],
)
