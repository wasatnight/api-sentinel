"""Feed initdb a password over a local Windows named pipe, never a plaintext file."""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes
from uuid import uuid4

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
]
kernel.CreateNamedPipeW.restype = wintypes.HANDLE
kernel.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel.WriteFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
pipe_name = r"\\.\pipe\sentinel-init-" + uuid4().hex
handle = kernel.CreateNamedPipeW(pipe_name, 2 | 0x80000, 8, 1, 4096, 4096, 10000, None)
if handle == wintypes.HANDLE(-1).value:
    raise ctypes.WinError(ctypes.get_last_error())
password = (os.environ.pop("SENTINEL_INIT_PASSWORD") + "\n").encode("ascii")
process = subprocess.Popen(
    [
        sys.argv[1],
        "-D",
        sys.argv[2],
        "-U",
        "sentinel_admin",
        "--pwfile=" + pipe_name,
        "--auth=scram-sha-256",
        "--encoding=UTF8",
        "--locale=C",
    ]
)
try:
    connected = kernel.ConnectNamedPipe(handle, None)
    if not connected and ctypes.get_last_error() != 535:
        raise ctypes.WinError(ctypes.get_last_error())
    written = wintypes.DWORD()
    if not kernel.WriteFile(
        handle, password, len(password), ctypes.byref(written), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.FlushFileBuffers(handle)
finally:
    kernel.CloseHandle(handle)
sys.exit(process.wait())
