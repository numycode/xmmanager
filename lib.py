# import os
import json

def load_config():
    with open('config.json', 'r') as file:
        global data
        data = json.load(file)
def xmrig_controller(command):
    global xmrig_status
    if command == "start":
        print("> Starting XMRig")
        xmrig_status = "True"
    elif command == "stop":
        print("> Exiting XMRig")
        xmrig_status = "False"
    elif command == "status":
        print("Is XMRig running?: " + xmrig_status)
    elif command == "exit":
        print("> Exiting")
        exit(1)
if __name__ == __name__:
    load_config()
    xmrig_controller("start")
    xmrig_controller("status")
    xmrig_controller("stop")
    xmrig_controller("status")
    xmrig_controller("exit")