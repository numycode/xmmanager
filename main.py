import rumps
import sys
import os
import logging
import libxmmanager as libxm

xmrig_status = False
logger = logging.getLogger(__name__)


def adjacent_to_app(name):
    # TODO: get rid of that ai slop below
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        app_parent = os.path.dirname(bundle)
        return os.path.join(app_parent, name)
    return os.path.join(os.path.dirname(__file__), name)


xmrig_path = adjacent_to_app("xmrig")
xmrig_command = [xmrig_path, "--cpu-priority=1"]


class Main(rumps.App):
    @rumps.clicked("Toggle XMRig")
    def mining_controller(self, sender):
        global xmrig_status
        sender.state = not sender.state
        xmrig_status = not xmrig_status
        if xmrig_status:
            xmrig_status = libxm.xmrig_start(xmrig_command)
        elif not xmrig_status:
            xmrig_status = libxm.xmrig_stop()

    @rumps.clicked("Quit")
    def quit(self, _):
        libxm.xmrig_stop()
        logger.info("Stopped XMRig")
        logger.info("Exiting...")
        sys.exit()


if __name__ == "__main__":
    try:
        libxm.init()
        Main("XMManager", quit_button=None).run()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        libxm.xmrig_stop()
        logger.info("Stopped XMRig")
        logger.info("Exiting...")
        sys.exit()
