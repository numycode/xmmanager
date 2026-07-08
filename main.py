import rumps
import os
import sys
import logging
import subprocess
import threading

from PyObjCTools import AppHelper

logger = logging.getLogger(__name__)

# Grace period after starting xmrig during which we poll for an immediate
# crash. Anything that exits inside this window almost certainly has a config
# or permission problem we want to surface, not hide behind a "running" menu
# state. Matches the original 0.25s sleep.
STARTUP_GRACE_SECONDS = 0.25
STARTUP_CHECK_INTERVAL = 0.05

# Timeouts used when stopping xmrig for shutdown paths (quit, exception
# handler) where the user is waiting on the app to exit. Kept short so the
# total wait stays well under macOS's 5s unresponsiveness threshold for a
# blocking main-thread Quit handler.
SHUTDOWN_SIGTERM_TIMEOUT = 1
SHUTDOWN_SIGKILL_TIMEOUT = 0.5

# Timeouts used for the user-facing toggle path. A bit more generous so a
# well-behaved xmrig can wind down its workers cleanly.
TOGGLE_SIGTERM_TIMEOUT = 3
TOGGLE_SIGKILL_TIMEOUT = 2


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
        # rumps.Timer used to poll xmrig during the startup grace window.
        # Reused across restarts; we always stop() before start() to avoid
        # leaking NSTimers into the run loop.
        self._startup_check_timer = rumps.Timer(
            self._check_xmrig_startup, STARTUP_CHECK_INTERVAL
        )
        # Counter of remaining seconds (in check-interval units) the grace
        # timer should keep firing for the most recent start.
        self._grace_remaining = 0

    @rumps.clicked("Toggle XMRig")
    def mining_controller(self, sender):
        # Reconcile stale menu state. rumps does NOT auto-toggle a checkmark
        # on click, so if xmrig died unexpectedly the checkmark can lie.
        # Trust process reality over the menu state, but only flip the menu
        # back when we are sure the user did not just click "stop".
        if sender.state and not self._is_running():
            logger.warning("Toggle was checked but xmrig is not running; reconciling")
            rumps.notification(
                "XMManager",
                "XMRig stopped unexpectedly",
                "Check xmmanager.log for details.",
            )
            self._set_toggle_state(False)
            return

        if self._is_running():
            self._stop_xmrig_async()
            # Leave the checkmark visible during the brief cleanup window so
            # the menu does not flicker. The background thread will clear it
            # via AppHelper.callAfter once the process is actually gone.
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
        # Synchronous shutdown. A daemon background thread would be killed
        # by the Python interpreter during Cocoa app teardown, leaving
        # xmrig running as an orphan. We accept a short blocking wait on
        # the main thread so SIGTERM/SIGKILL actually land before the app
        # exits. SHUTDOWN_* timeouts keep the total under ~1.5s.
        try:
            self._stop_xmrig_sync(
                sigterm_timeout=SHUTDOWN_SIGTERM_TIMEOUT,
                sigkill_timeout=SHUTDOWN_SIGKILL_TIMEOUT,
            )
        except Exception as e:
            logger.error(f"Error stopping xmrig on quit: {e}")
        logger.info("Exiting...")
        rumps.quit_application()

    def _is_running(self):
        proc = self.xmrig_process
        return proc is not None and proc.poll() is None

    def _set_toggle_state(self, new_state):
        """Set the checkmark on the toggle menu item.

        Must be called on the main thread. Current call sites all satisfy
        that: rumps click handlers run on the main run loop, the grace
        timer's callback fires on the main run loop, and the background
        _stop_xmrig_async thread hops back here via AppHelper.callAfter
        before calling this method.
        """
        # self.menu is a dict-like view of the NSMenu built at run() time.
        # Look up the item by title so timer / background-thread callbacks
        # can update state without a sender reference.
        self.menu["Toggle XMRig"].state = new_state

    def _start_xmrig(self):
        """Start xmrig. Returns True once Popen succeeds and the grace
        timer has been armed. The grace timer is responsible for detecting
        an immediate crash and reverting the toggle state."""
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
        except OSError as e:
            logger.error(f"Error starting xmrig: {e}")
            self.xmrig_process = None
            return False

        # Arm the grace timer. Runs on the main run loop, so it is safe to
        # touch menu state from the callback without thread-safe dispatch.
        self._grace_remaining = STARTUP_GRACE_SECONDS
        self._startup_check_timer.stop()
        self._startup_check_timer.start()

        logger.info("Started XMRig")
        return True

    def _check_xmrig_startup(self, _timer):
        """Timer callback fired on the main run loop during the startup
        grace window. If xmrig died before the window expired, revert the
        toggle state so the menu does not lie about whether mining is on."""
        # If the process was stopped (or never finished starting) before
        # the grace window elapsed, just stop polling and bail.
        if self.xmrig_process is None:
            self._startup_check_timer.stop()
            return

        # Crashed early? Revert the toggle so the UI matches reality.
        # Checked before the grace-expiry branch so a crash on the final
        # tick is not silently swallowed by the time-up early return.
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

        # Time's up: xmrig survived the grace window, treat it as running.
        self._grace_remaining -= STARTUP_CHECK_INTERVAL
        if self._grace_remaining <= 0:
            self._startup_check_timer.stop()

    def _stop_xmrig_async(self):
        """Stop xmrig on a background thread. Safe to call from main-thread
        callbacks (rumps click handlers) because the actual terminate/wait/
        kill can take up to ~5s and we must not block the macOS main run
        loop. Quit uses _stop_xmrig_sync instead because the interpreter
        kills daemon threads during shutdown."""
        proc = self.xmrig_process
        if proc is None or proc.poll() is not None:
            self.xmrig_process = None
            return

        # Cancel the grace timer. If the user stops during the startup
        # window, the timer would otherwise fire on the next tick, see the
        # process exiting via SIGTERM, and post a spurious "XMRig stopped
        # unexpectedly" notification.
        self._startup_check_timer.stop()

        # Snapshot the handle so a subsequent start (e.g. user toggles back
        # on before cleanup finishes) cannot race with this thread.
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
                # Only clear the live handle if it is still the one we
                # were stopping. A restart in the meantime would have
                # replaced self.xmrig_process with a new Popen.
                if self.xmrig_process is target:
                    self.xmrig_process = None
                # Hop back to the main thread for the menu update.
                AppHelper.callAfter(self._set_toggle_state, False)
                logger.info("Stopped XMRig")

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
        main_app = Main("XMManager", quit_button=None)
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
                # Never let a stop failure prevent the force-exit; an
                # orphaned xmrig is the lesser evil compared to a
                # process that won't quit at all.
                logger.error(f"Error stopping xmrig in __main__ handler: {stop_err}")
        logger.info("Force exiting...")
        os._exit(0)
