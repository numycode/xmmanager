import rumps
import os
import sys
import logging
import subprocess
import threading

from PyObjCTools import AppHelper

logger = logging.getLogger(__name__)

STARTUP_GRACE_SECONDS = 0.25
STARTUP_CHECK_INTERVAL = 0.05
SHUTDOWN_SIGTERM_TIMEOUT = 1
SHUTDOWN_SIGKILL_TIMEOUT = 0.5
TOGGLE_SIGTERM_TIMEOUT = 3
TOGGLE_SIGKILL_TIMEOUT = 2


def init(filename="xmmanager.log"):
    logging.basicConfig(filename=filename, level=logging.INFO)
    logger.info("Initialized logger")


def find_xmrig():
    def _is_xmrig(path):
        return (
            path
            and os.path.isfile(path)
            and os.access(path, os.X_OK)
        )

    # env
    env = os.environ.get("XMRIG_PATH")
    if _is_xmrig(env):
        logger.info(f"Using xmrig from XMRIG_PATH: {env}")
        return env

    # brew/ports
    for path in (
        "/opt/homebrew/bin/xmrig",
        "/usr/local/bin/xmrig",
        "/opt/local/bin/xmrig",
    ):
        if _is_xmrig(path):
            logger.info(f"Found xmrig at {path}")
            return path

    # bin
    home = os.path.expanduser("~")
    for path in (
        os.path.join(home, ".local", "bin", "xmrig"),
    ):
        if _is_xmrig(path):
            logger.info(f"Found xmrig at {path}")
            return path
    # next to .app
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(
            os.path.dirname(os.path.dirname(sys.executable))
        )
        adjacent = os.path.join(os.path.dirname(bundle), "xmrig")
        if _is_xmrig(adjacent):
            logger.info(f"Found xmrig at {adjacent}")
            return adjacent
    # next to main
    if not getattr(sys, "frozen", False):
        dev_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "xmrig"
        )
        if _is_xmrig(dev_path):
            logger.info(f"Found xmrig at {dev_path}")
            return dev_path

    logger.error(
        "XMRig not found. Install via "
        "`brew install xmrig` or set the XMRIG_PATH environment variable."
    )
    return None


class Main(rumps.App):
    def __init__(self, *args, xmrig_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.xmrig_path = xmrig_path
        self.xmrig_config = os.path.expanduser("~/.xmrig.json")
        self.xmrig_command = (
            [
                xmrig_path,
                "--cpu-priority=0",
                f"--config={self.xmrig_config}",
            ]
            if xmrig_path
            else None
        )
        self.xmrig_process = None
        self._startup_check_timer = rumps.Timer(
            self._check_xmrig_startup, STARTUP_CHECK_INTERVAL
        )
        self._grace_remaining = 0
        self._grace_target = None
        self._missing_quit_timer = rumps.Timer(
            self._handle_missing_xmrig, 0.1
        )

    @rumps.clicked("Toggle XMRig")
    def mining_controller(self, sender):
        if sender.state and not self._is_running():
            logger.warning("Toggle was checked but xmrig is not running; reconciling")
            self.xmrig_process = None
            self._startup_check_timer.stop()
            self._grace_target = None
            rumps.notification(
                "XMManager",
                "XMRig stopped unexpectedly",
                "Check xmmanager.log for details.",
            )
            self._set_toggle_state(False)
            return

        if self._is_running():
            self._stop_xmrig_async()
            return

        if self._start_xmrig():
            self._set_toggle_state(True)
        else:
            self._set_toggle_state(False)
            rumps.notification(
                "XMManager",
                "Failed to start XMRig",
                "Check xmmanager.log for details.",
            )

    @rumps.clicked("Quit")
    def on_quit(self, _):
        try:
            self._stop_xmrig_sync(
                sigterm_timeout=SHUTDOWN_SIGTERM_TIMEOUT,
                sigkill_timeout=SHUTDOWN_SIGKILL_TIMEOUT,
            )
        except Exception as e:
            logger.error(f"Error stopping xmrig on quit: {e}")
        logger.info("Exiting...")
        rumps.quit_application()

    def run(self, *args, **kwargs):
        if self.xmrig_path is None:
            self._missing_quit_timer.start()
        super().run(*args, **kwargs)

    def _handle_missing_xmrig(self, _timer):
        """One-shot callback: tell the user xmrig is missing, then exit.

        Fires from a rumps.Timer started in run() (not __init__) so the
        NSApp run loop is already up. The timer is repeating under the
        hood, so we stop it before doing anything to guarantee this is
        actually one-shot.
        """
        self._missing_quit_timer.stop()
        rumps.notification(
            "XMManager",
            "XMRig not found",
            "Install with `brew install xmrig`, or set the XMRIG_PATH "
            "environment variable to the binary location. See the README.",
        )
        rumps.quit_application()

    def _is_running(self):
        proc = self.xmrig_process
        return proc is not None and proc.poll() is None

    def _set_toggle_state(self, new_state):
        self.menu["Toggle XMRig"].state = new_state

    def _start_xmrig(self):
        if self.xmrig_command is None:
            logger.error("Cannot start xmrig: binary path not resolved")
            return False
        if self._is_running():
            return True
        try:
            self.xmrig_process = subprocess.Popen(
                self.xmrig_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as e:
            logger.error(f"Error starting xmrig: {e}")
            self.xmrig_process = None
            return False
        self._grace_target = self.xmrig_process
        self._grace_remaining = STARTUP_GRACE_SECONDS
        self._startup_check_timer.stop()
        self._startup_check_timer.start()

        logger.info("Started XMRig")
        return True

    def _check_xmrig_startup(self, _timer):
        if self._grace_target is not self.xmrig_process:
            self._startup_check_timer.stop()
            return
        if self.xmrig_process.poll() is not None:
            rc = self.xmrig_process.returncode
            logger.error(f"xmrig exited immediately with code {rc}")
            self.xmrig_process = None
            self._startup_check_timer.stop()
            self._set_toggle_state(False)
            rumps.notification(
                "XMManager",
                "XMRig stopped unexpectedly",
                f"Exited with code {rc}. Check xmmanager.log for details.",
            )
            return

        self._grace_remaining -= STARTUP_CHECK_INTERVAL
        if self._grace_remaining <= 0:
            self._startup_check_timer.stop()

    def _stop_xmrig_async(self):
        proc = self.xmrig_process
        if proc is None or proc.poll() is not None:
            self.xmrig_process = None
            return
        self._startup_check_timer.stop()
        target = proc

        def _shutdown():
            try:
                target.terminate()
                try:
                    target.wait(timeout=TOGGLE_SIGTERM_TIMEOUT)
                except subprocess.TimeoutExpired:
                    logger.warning("xmrig did not exit after SIGTERM, sending SIGKILL")
                    target.kill()
                    target.wait(timeout=TOGGLE_SIGKILL_TIMEOUT)
            except (OSError, ProcessLookupError, subprocess.TimeoutExpired) as e:
                logger.error(f"Error stopping xmrig: {e}")
            finally:
                if self.xmrig_process is target:
                    self.xmrig_process = None
                    AppHelper.callAfter(self._set_toggle_state, False)
                    logger.info("Stopped XMRig")
                else:
                    logger.info(
                        f"Skipping UI update for stopped xmrig (pid {target.pid}); "
                        f"a new process has taken its place"
                    )

        threading.Thread(target=_shutdown, daemon=True).start()

    def _stop_xmrig_sync(self, sigterm_timeout, sigkill_timeout):
        """Synchronous stop for shutdown paths (exception handler) where
        we are about to os._exit anyway and want a best-effort clean
        termination first."""
        proc = self.xmrig_process
        if proc is None or proc.poll() is not None:
            self.xmrig_process = None
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=sigterm_timeout)
            except subprocess.TimeoutExpired:
                logger.warning("xmrig did not exit after SIGTERM, sending SIGKILL")
                proc.kill()
                proc.wait(timeout=sigkill_timeout)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired) as e:
            logger.error(f"Error stopping xmrig: {e}")
        finally:
            self.xmrig_process = None
        logger.info("Stopped XMRig")


if __name__ == "__main__":
    main_app = None
    try:
        init()
        xmrig = find_xmrig()
        main_app = Main("XMManager", xmrig_path=xmrig, quit_button=None)
        main_app.run()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        if main_app is not None:
            try:
                main_app._stop_xmrig_sync(
                    sigterm_timeout=SHUTDOWN_SIGTERM_TIMEOUT,
                    sigkill_timeout=SHUTDOWN_SIGKILL_TIMEOUT,
                )
            except Exception as stop_err:
                logger.error(f"Error stopping xmrig in __main__ handler: {stop_err}")
        logger.info("Force exiting...")
        os._exit(0)
