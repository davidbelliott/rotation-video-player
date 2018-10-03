# rotation-video-player

Player application for the 2018 Avery Rotation Video, "Averoid Adventures."

## Prerequisites

Target system must have `python` > 3.6, `ffplay`, and the rotation video file saved as `videos/main.mp4` relative to this repository root. Download the (censored) rotation video file here: [main.mp4](https://mega.nz/#!SOR2QYiS!lNGszKAf18C59WbDnayJgLdX_F5tQ3N18NIFxUIMpeY). Use `pip install -r requirements.txt` to install required Python packages using `pip`. Finally, you must run the rotation video server [available here](https://github.com/davidbelliott/rotation-video-server) on the same machine, or on a machine with a different IP address as long as you update the constant `SERVER_URL` in `player.py` to the new address.

## Usage

Once you have installed all necessary prerequisites and started the rotation video server, run the player using `./player.py map.json`. A video window should begin to play the rotation video. Connect to the rotation video server in a web browser, and clickable choices should appear on the webpage when the rotation video reaches a choice point.

## Troubleshooting

If execution freezes before the video appears, it is likely because the player is still waiting for a connection to the server. Ensure that the server is configured properly and that `SERVER_URL` in `player.py` points to the correct endpoint.
