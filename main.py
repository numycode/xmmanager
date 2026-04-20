import rumps
#import os
mining_status = False
def check_mining_status():
    if mining_status == False:
        return "Start Mining"
    else:
        return "Stop Mining"
name_status = check_mining_status()
class main(rumps.App):
    @rumps.clicked(name_status)
    def mining_controller(self, _):
        if mining_status == True:
            mining_status = False
        else:
            mining_status = True
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