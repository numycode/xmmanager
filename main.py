import rumps
import os
import sys
import logging
import subprocess
import time

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Popen handle for the running xmrig, or None when stopped.
        # Source of truth for the toggle state.
        self.xmrig_process = None

    @rumps.clicked("Toggle XMRig")
    def mining_controller(self, sender):
        # Decide first, then flip the menu. Flipping the menu before
        # we know whether xmrig actually started was the original bug.
        if self._is_running():
            self._stop_xmrig()
            sender.state = False
            return

        if self._start_xmrig():
            sender.state = True
        else:
            sender.state = False
            rumps.notification(
                "XMManager",
                "Failed to start XMRig",
                "Check xmmanager.log for details.",
            )

    @rumps.clicked("Quit")
    def on_quit(self, _):
        self._stop_xmrig()
        logger.info("Exiting...")
        rumps.quit_application()

    def _is_running(self):
        proc = self.xmrig_process
        return proc is not None and proc.poll() is None

    def _start_xmrig(self):
        """Start xmrig. Returns True only after it looks like it is running."""
        if self._is_running():
            return True
        try:
            self.xmrig_process = subprocess.Popen(
                xmrig_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Put xmrig in its own process group so signals we receive
                # on the menu bar app don't leak into the child.
                start_new_session=True,
            )
        except (OSError, FileNotFoundError) as e:
            logger.error(f"Error starting xmrig: {e}")
            self.xmrig_process = None
            return False

        # Give xmrig a brief grace period to die on bad config / bad
        # binary. Anything that exits inside this window almost certainly
        # has a config or permission problem we want to surface, not hide
        # behind a "running" menu state.
        time.sleep(0.25)
        if self.xmrig_process.poll() is not None:
            rc = self.xmrig_process.returncode
            logger.error(f"xmrig exited immediately with code {rc}")
            self.xmrig_process = None
            return False

        logger.info("Started XMRig")
        return True

    def _stop_xmrig(self):
        """Stop the running xmrig, if any. Safe to call multiple times."""
        proc = self.xmrig_process
        if proc is None or proc.poll() is not None:
            self.xmrig_process = None
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logger.warning("xmrig did not exit after SIGTERM, sending SIGKILL")
                proc.kill()
                proc.wait(timeout=2)
        except (OSError, ProcessLookupError) as e:
            logger.error(f"Error stopping xmrig: {e}")
        finally:
            self.xmrig_process = None
        logger.info("Stopped XMRig")


if __name__ == "__main__":
    main_app = None
    try:
        init()
        main_app = Main("XMManager", quit_button=None)
        main_app.run()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        if main_app is not None:
            main_app._stop_xmrig()
        logger.info("Force exiting...")
        os._exit(0)
