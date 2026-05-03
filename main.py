import rumps
import json
import subprocess
import traceback
xmrig_status = False

def xmrig_start(xmrig_status):
  try:
    subprocess.Popen(config["path"] + " -B " + config["args"], shell=True)
    return True
  except Exception:
    traceback.print_exc()
def xmrig_stop(xmrig_status):
  try:
    subprocess.Popen(config["kill-command"], shell=True)
    return False
  except Exception:
    traceback.print_exc()



class main(rumps.App):
  @rumps.clicked(str(xmrig_status))
  def mining_controller(self, sender):
    sender.state = not sender.state
    xmrig_status = not xmrig_status
    if xmrig_status == False:
      xmrig_status = xmrig_start(xmrig_status)
    if xmrig_status == True:
      xmrig_status = xmrig_stop(xmrig_status)
  @rumps.clicked("Quit")
  def quit(self, _):
    xmrig_status = xmrig_stop(xmrig_status)
    exit()
if __name__ == "__main__":
  with open('xmmanager_config.json', 'r') as file:
    config = json.load(file)
    try:
      main("XMManager", quit_button=None).run()
    except Exception as e:
      print("Exeption: " + e)
      xmrig_status = xmrig_stop(xmrig_status)
      exit()