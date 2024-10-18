#!/bin/sh

rm -f /tmp/.X0-lock

# Run Xvfb on dispaly 0.
Xvfb :0 -screen 0 1280x720x16 &

# Run fluxbox windows manager on display 0.
fluxbox -display :0 &

# Run x11vnc on display 0
x11vnc -display :0 -forever -ncache 10 &

# Add delay
sleep 5

. .venv/bin/activate && python3 main.py