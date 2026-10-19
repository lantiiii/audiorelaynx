#!/usr/bin/env python3
"""Streams Windows system audio to the Switch NRO (WASAPI loopback).

Usage:  python pc_sender_wasapi.py SWITCH_IP [port]
Install: python -m pip install pyaudiowpatch numpy

Tip: set your Windows output device to 48000 Hz (Sound settings >
Device properties > Advanced / Format) so no resampling is needed.
"""
import socket
import sys
import time

import numpy as np
import pyaudiowpatch as pyaudio

OUT_RATE = 48000
BLOCK_MS = 20


def find_loopback(p):
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    spk = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
    if spk.get("isLoopbackDevice"):
        return spk
    for lb in p.get_loopback_device_info_generator():
        if spk["name"] in lb["name"]:
            return lb
    raise RuntimeError("No loopback device found for default output")


def connect(ip, port):
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, port))
            s.settimeout(None)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16384)
            print(f"Connected to {ip}:{port}", flush=True)
            return s
        except OSError as e:
            print(f"Waiting for Switch ({e})...", flush=True)
            time.sleep(2)


def to_switch_format(raw, ch, rate):
    a = np.frombuffer(raw, dtype="<i2").reshape(-1, ch)
    st = np.repeat(a, 2, axis=1) if ch == 1 else a[:, :2]
    if rate != OUT_RATE:
        n_out = int(len(st) * OUT_RATE / rate)
        x_old = np.linspace(0, 1, len(st), endpoint=False)
        x_new = np.linspace(0, 1, n_out, endpoint=False)
        st = np.column_stack(
            [np.interp(x_new, x_old, st[:, c]) for c in range(2)]
        )
    return np.clip(st, -32768, 32767).astype("<i2").tobytes()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ip = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    p = pyaudio.PyAudio()
    dev = find_loopback(p)
    rate = int(dev["defaultSampleRate"])
    ch = int(dev["maxInputChannels"])
    frames = int(rate * BLOCK_MS / 1000)
    print(f"Capturing: {dev['name']} ({rate} Hz, {ch} ch)", flush=True)
    if rate != OUT_RATE:
        print("Note: resampling to 48000 Hz; set the device to 48000 Hz for best quality.")

    stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True,
                    input_device_index=dev["index"], frames_per_buffer=frames)

    try:
        while True:
            sock = connect(ip, port)
            try:
                while True:
                    raw = stream.read(frames, exception_on_overflow=False)
                    sock.sendall(to_switch_format(raw, ch, rate))
            except OSError as e:
                print(f"Connection lost ({e}), reconnecting...", flush=True)
                sock.close()
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    main()
