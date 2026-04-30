import subprocess
import json

def load_config():
    with open('config.json', 'r') as file:
        global config
        config = json.load(file)
def xmrig_controller(command):
    global xmrig_status
    if command == "start":
        subprocess.call(config["path"] + " -B " + config["args"], shell=True)
        xmrig_status = "True"
    elif command == "stop":
        subprocess.call(config["kill-command"], shell=True)
        xmrig_status = "False"
    elif command == "exit":
        exit(1)
def toggler(xmrig_status):
    if xmrig_status == "True":
        return "Stop XMRig"
    elif xmrig_status == "False":
        return "Start XMRig"
    else:
        return "ERROR: xmrig_status is not the str True or False"
if __name__ == __name__:
    pass