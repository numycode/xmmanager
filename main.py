import rumps
import os
import sys
import logging
import subprocess

xmrig_status = False
logger = logging.getLogger(__name__)

def init(filename="xmmanager.log"):
    logging.basicConfig(filename=filename, level=logging.INFO)
    logger.info("Initialized logger")

def adjacent_to_app(name):
    # TODO: get rid of that ai slop below
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        app_parent = os.path.dirname(bundle)
        return os.path.join(app_parent, name)
    return os.path.join(os.path.dirname(__file__), name)


xmrig_path = adjacent_to_app("xmrig")
xmrig_command = [xmrig_path, "--cpu-priority=0"]

class Main(rumps.App):
    @rumps.clicked("Toggle XMRig")
    def mining_controller(self, sender):
        global xmrig_status
        sender.state = not sender.state
        xmrig_status = not xmrig_status
        if xmrig_status:
            try:
                xmrig = subprocess.Popen(xmrig_command)
                xmrig_status = (xmrig is not None and xmrig.poll() is None)
            except Exception as e:
                logger.error(f"Error at xmrig_start: {e}")
            logger.info("Started XMRig")
            return True
        elif not xmrig_status:
            subprocess.Popen(["pkill", "xmrig"])
            logger.info("Stopped XMRig")
            xmrig_status = False

    @rumps.clicked("Quit")
    def on_quit(self, _):
        subprocess.Popen(["pkill", "xmrig"])
        logger.info("Stopped XMRig")
        logger.info("Exiting...")
        rumps.quit_application()
        sys.exit(0)


if __name__ == "__main__":
    try:
        init()
        Main("XMManager", quit_button=None).run()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        subprocess.Popen(["pkill", "xmrig"])
        logger.info("Stopped XMRig")
        logger.info("Force exiting...")
        os._exit(0)
