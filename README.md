usage:
Open PowerShell
enter this: python audiorelay.py [switch ip]
it automatically detects the port, so no need to enter port with it
if you get buffering issues, edit the python file:
by default, cushion_blocks=2, each one is a 20ms delay. if audio is buffering, add more blocks
