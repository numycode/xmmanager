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
        lib.xmrig_controller("exit")
if __name__ == "__main__":
    lib.load_config()
    try:
        main("XMManager", quit_button=None).run()
    except:
        lib.xmrig_controller("stop")
        exit()
pass