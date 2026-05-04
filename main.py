import rumps
import json
import subprocess
import sys
import os
global xmrig_status
xmrig_status = False

def xmrig_start():
  with open('xmmanager_config.json', 'r') as file:
    config = json.load(file)
  subprocess.Popen(xmrig_path + " " + config["args"], shell=True)
  return True
def xmrig_stop():
  subprocess.Popen("pkill xmrig", shell=True)
  return False

def adjacent_to_app(name):
    # TODO: get rid of that ai slop below
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        app_parent = os.path.dirname(bundle)
        return os.path.join(app_parent, name)
    return os.path.join(os.path.dirname(__file__), name)

xmrig_path = adjacent_to_app("xmrig")



class main(rumps.App):
  @rumps.clicked("Toggle XMRig")
  def mining_controller(self, sender):
    global xmrig_status
    sender.state = not sender.state
    xmrig_status = not xmrig_status
    if xmrig_status:
      xmrig_status = xmrig_start()
    elif xmrig_status == False:
      xmrig_status = xmrig_stop()
  @rumps.clicked("Quit")
  def quit(self, _):
    global xmrig_status
    xmrig_status = xmrig_stop()
    rumps.quit_application()
    sys.exit()
if __name__ == "__main__":
    try:
      main("XMManager", quit_button=None).run()
    except Exception as e:
      print(f"Exception: {e}")
      xmrig_status = xmrig_stop()
      sys.exit()