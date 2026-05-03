import rumps
import json
import subprocess
import sys
global xmrig_status
xmrig_status = False

def xmrig_start(xmrig_status):
  with open('xmmanager_config.json', 'r') as file:
    config = json.load(file)
  subprocess.Popen(config["path"] + " -B " + config["args"], shell=True)
  return True
def xmrig_stop(xmrig_status):
  with open('xmmanager_config.json', 'r') as file:
    config = json.load(file)
  subprocess.Popen(config["kill-command"], shell=True)
  return False



class main(rumps.App):
  @rumps.clicked("Toggle XMRig")
  def mining_controller(self, sender):
    global xmrig_status
    sender.state = not sender.state
    xmrig_status = not xmrig_status
    print(xmrig_status)
    if xmrig_status == True:
      xmrig_status = xmrig_start(xmrig_status)
    elif xmrig_status == False:
      print("Running")
      xmrig_status = xmrig_stop(xmrig_status)
  @rumps.clicked("Quit")
  def quit(self, _):
    global xmrig_status
    xmrig_status = xmrig_stop(xmrig_status)
    rumps.quit_application()
    sys.exit()
if __name__ == "__main__":
    try:
      main("XMManager", quit_button=None).run()
    except Exception as e:
      print(f"Exception: {e}")
      xmrig_status = xmrig_stop(xmrig_status)
      sys.exit()