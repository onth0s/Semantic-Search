"""Cross-platform clipboard utility using native Windows clip.exe or subprocess fallbacks."""

from __future__ import annotations

import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Copy *text* string to the system clipboard.

    Returns True if successfully copied, False otherwise.
    """
    if not text:
        return False

    try:
        if sys.platform == "win32":
            # Native Windows clip.exe
            proc = subprocess.Popen(
                ["clip.exe"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                shell=False,
            )
            proc.communicate(input=text.encode("utf-16le"))
            return proc.returncode == 0
        elif sys.platform == "darwin":
            # macOS pbcopy
            proc = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )
            proc.communicate(input=text.encode("utf-8"))
            return proc.returncode == 0
        else:
            # Linux xclip / xsel
            for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
                    proc.communicate(input=text.encode("utf-8"))
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
            return False
    except Exception:
        return False
