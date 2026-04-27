import rumps
import subprocess
import json
from lib import *
class main(rumps.App):
    @rumps.clicked(name_status)
    def mining_controller(self, _):

#    def onoff(self, sender):
#        sender.state = not sender.state

    @rumps.clicked("Say hi")
    def sayhi(self, _):
        rumps.notification("Awesome title", "amazing subtitle", "hi!!1")

    @rumps.clicked("Preferences")
    def prefs(self, _):
        rumps.alert("test!")
if __name__ == "__main__":
    main("XMManager").run()
pass