# XMManager

[![macOS build](https://github.com/numycode/xmmanager/actions/workflows/macos-build.yml/badge.svg)](https://github.com/numycode/xmmanager/actions/workflows/macos-build.yml)

XMManager is an easy way to manage XMRig on your Mac. It currently allows you to toggle XMRig for easy use of the miner.

# Install
### Using prebuilt:
1. Download from releases and drag `XMManager.app` to `/Applications`
2. Install [XMRig](https://xmrig.com/download) somewhere XMManager can find it. The easiest way is `brew install xmrig`, which puts it at `/opt/homebrew/bin/xmrig` (Apple Silicon) or `/usr/local/bin/xmrig` (Intel). Other places XMManager checks automatically:
	- `$XMRIG_PATH` environment variable (highest priority, useful for custom installs)
	- `/opt/homebrew/bin/xmrig`, `/usr/local/bin/xmrig`, `/opt/local/bin/xmrig` (Homebrew / MacPorts)
	- `~/bin/xmrig`, `~/.local/bin/xmrig`
	- The same folder as `XMManager.app` (legacy "sidecar" install)
	- Warning - XMRig can get flagged by your antivirus due to malicious programs using it to mine without permission. XMRig is a safe program.
3. Create a [config.json](https://xmrig.com/docs/miner/config) file and place it in the working directory where you launch XMManager. (Command line arguments are not yet supported.)
4. Run XMManager and have fun mining!

If XMManager can't find xmrig at startup, it shows a notification and quits instead of staying open with a dead toggle. Set `XMRIG_PATH=/full/path/to/xmrig` in your shell profile if you installed it somewhere unusual.
### From source:

I don't even remember at this point, too much debugging. I'll add CI soon so I'll update this part once I understand how I built it.

# Usage
Start the app first, then look at your menu bar. You should see a new entry called "XMManager".

![An entry in a mac OS menu bar with the text "XMManager"](images/xmmanager-closed-off.png)

Click on it to open the menu.

![A menu bar menu named "XMManager" with two options; "Toggle XMRig" which is toggled off, and "Quit"](images/xmmanager-open-off.png)

Quit does as you would expect, it quits the program and also quits XMRig. Toggle XMRig, when you click it, either starts XMRig or kills it. When you click it, it changes to this:

![The same menu as the last picture, but "Toggle XMRig" has a check mark next to it](images/xmmanager-open-on.png)

The check mark signifies that XMRig is running. You can click it again and XMRig will be killed.<br>
Watch the video [here](https://cdn.hackclub.com/019df076-974f-7d73-9d7f-e3ed8fa12d0d/xmmanager.mp4) to see XMManager in action.<br>
And that is it! Have fun mining!

## AI Notice
AI was used in this repository for the GitHub Actions runner, a function flagged for later replacement, CI debugging, and the `mining_controller` refactor that fixed the toggle race and replaced `pkill` with proper PID handling. The rest is human-written.

## Contributors
- [@rocklake](https://codeberg.org/rocklake/) ([rocklake's GitHub](https://github.com/rocklake/)) - Helped get the code into a usable state since the whole codebase was crumbling 
