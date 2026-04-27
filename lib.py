import subprocess
import json

def load_config():
    with open('config.json', 'r') as file:
        global config
        config = json.load(file)
def xmrig_controller(command):
    global xmrig_status
    if command == "start":
        print("> Starting XMRig")
        subprocess.call(config["path"] + " -B " + config["args"], shell=True)
        xmrig_status = "True"
        print("> Started.")
    elif command == "stop":
        print("> Exiting XMRig")
        subprocess.call(config["kill-command"], shell=True)
        xmrig_status = "False"
        print("> Exited.")
    elif command == "status":
        print("Is XMRig running?: " + xmrig_status)
    elif command == "exit":
        print("> Exiting")
        exit(1)
if __name__ == __name__:
    pass