"""Windows DPAPI decryption; encrypted files are bound to the current Windows user."""

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


def decrypt_windows_secret(path: Path) -> str:
    if os.name != "nt":
        raise RuntimeError("Use SENTINEL_DB_PASSWORD outside Windows; DPAPI is Windows-only.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    raw = bytes.fromhex(path.read_text(encoding="utf-8-sig").strip())
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source = Blob(len(raw), buffer)
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    local_free = ctypes.WinDLL("kernel32").LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    if not crypt.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
    ):
        raise RuntimeError("Could not decrypt the local PostgreSQL password.")
    try:
        return ctypes.string_at(target.data, target.size).decode("utf-16-le")
    finally:
        local_free(target.data)
