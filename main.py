import rumps
import json
import subprocess
xmrig_status = "False"

def xmrig_controller(command):
    global xmrig_status
    if command == "start":
        subprocess.call(config["path"] + " -B " + config["args"], shell=True)
        xmrig_status = "True"
    elif command == "stop":
        subprocess.call(config["kill-command"], shell=True)
        xmrig_status = "False"

def toggler(xmrig_status):
    if xmrig_status == "True":
        return "Stop XMRig"
    elif xmrig_status == "False":
        return "Start XMRig"
    else:
        return "ERROR: xmrig_status is not the str True or False"

class main(rumps.App):
    @rumps.clicked(toggler(xmrig_status))
    def mining_controller(self, sender):
        sender.state = not sender.state
        if xmrig_status == "False":
            xmrig_controller("start")
        if xmrig_status == "True":
            xmrig_controller("stop")
    @rumps.clicked("Quit")
    def quit(self, _):
        xmrig_controller("stop")
        exit()
if __name__ == "__main__":
    with open('xmmanager_config.json', 'r') as file:
        config = json.load(file)
    try:
        main("XMManager", quit_button=None).run()
    except Exception as e:
        print("Exeption: " + e)
        xmrig_controller("stop")
        exit()
pass 