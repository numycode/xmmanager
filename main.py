import rumps
import lib
from lib import *
xmrig_status = "False"
class main(rumps.App):
    @rumps.clicked(toggler(xmrig_status))
    def mining_controller(self, _):
        if xmrig_status == "False":
            xmrig_controller("start")
        if xmrig_status == "True":
            xmrig_controller("stop")
    @rumps.clicked("Quit")
    def quit(self, _):
        lib.xmrig_controller("stop")
        exit()
if __name__ == "__main__":
    with open('xmmanager_config.json', 'r') as file:
        config = json.load(file)
    try:
        main("XMManager", quit_button=None).run()
    except Exception as e:
        print("Exeption: " + e)
        lib.xmrig_controller("stop")
        exit()
pass 