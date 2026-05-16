import rumps
import sys
import os
import logging
import libxmmanager as libxm

xmrig_status = False
args = "--cpu-priority=1"
logger = logging.getLogger(__name__)

# def xmrig_start():
#   with open('xmmanager_config.json', 'r') as file:
#     config = json.load(file)
#   subprocess.Popen(xmrig_path + " " + config["args"], shell=True)
#   return True
# def xmrig_stop():
#   subprocess.Popen("pkill xmrig", shell=True)
#   return False

def adjacent_to_app(name):
    # TODO: get rid of that ai slop below
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        app_parent = os.path.dirname(bundle)
        return os.path.join(app_parent, name)
    return os.path.join(os.path.dirname(__file__), name)

xmrig_path = adjacent_to_app("xmrig")



class Main(rumps.App):
  @rumps.clicked("Toggle XMRig")
  def mining_controller(self, sender):
    global xmrig_status
    sender.state = not sender.state
    xmrig_status = not xmrig_status
    if xmrig_status:
      xmrig_status = libxm.xmrig_start(xmrig_path, args)
    elif not xmrig_status:
      xmrig_status = libxm.xmrig_stop()
  @rumps.clicked("Quit")
  def quit(self, _):
    libxm.kill()
if __name__ == "__main__":
    try:
        libxm.init()
        Main("XMManager", quit_button=None).run()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        libxm.kill()