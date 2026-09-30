"""The address the phone should open. Works with no internet, as long as there's a LAN."""

from __future__ import annotations

import socket
import subprocess


def lan_ip() -> str:
    # Routing trick: "connecting" a UDP socket sends nothing but picks the outgoing interface.
    for probe in ("10.255.255.255", "192.168.255.255", "172.31.255.255"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 1))
                ip = s.getsockname()[0]
                if not ip.startswith("127."):
                    return ip
        except OSError:
            continue
    for iface in ("en0", "en1", "bridge100"):  # macOS Wi-Fi, Ethernet, Internet Sharing
        try:
            ip = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True, timeout=1).stdout.strip()
            if ip:
                return ip
        except (OSError, subprocess.SubprocessError):
            continue
    return "127.0.0.1"


def public_url(configured: str, port: int) -> str:
    return configured.rstrip("/") if configured else f"http://{lan_ip()}:{port}"
