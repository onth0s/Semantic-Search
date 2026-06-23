"""Low-level Windows NTFS USN Journal scanner.

Uses ctypes to open read-only raw volume handles and call DeviceIoControl
to enumerate all files and folders via FSCTL_ENUM_USN_DATA.
"""

from __future__ import annotations

import ctypes
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Windows API Constants & Typedefs
# ---------------------------------------------------------------------------

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = -1

FSCTL_QUERY_USN_JOURNAL = 0x000900F4
FSCTL_ENUM_USN_DATA = 0x000900B3

MFT_ROOT_INDEX = 5
MFT_INDEX_MASK = 0xFFFFFFFFFFFF  # Lower 48 bits of File Reference Number

if sys.platform == "win32":
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE

    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


def is_invalid_handle(handle) -> bool:
    """Check if the volume handle is None or set to an invalid handle value."""
    return handle in (None, INVALID_HANDLE_VALUE, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)


def is_admin() -> bool:
    """Check if the current process has administrative privileges on Windows."""
    if sys.platform != "win32":
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_mft_index(frn: int) -> int:
    """Extract the MFT index (lower 48 bits) from a File Reference Number."""
    return frn & MFT_INDEX_MASK


def scan_volume_files(volume_letter: str, search_root: Path) -> list[Path] | None:
    """Scan an NTFS volume using USN Journal and return descendants of search_root.

    Args:
        volume_letter: E.g., 'C' or 'D'.
        search_root: Path object to filter descendants.

    Returns:
        List of Path objects if successful, or None if USN query/enumeration fails.
    """
    if sys.platform != "win32":
        return None

    volume_path = f"\\\\.\\{volume_letter.upper()}:"
    h_volume = ctypes.windll.kernel32.CreateFileW(
        volume_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )

    if is_invalid_handle(h_volume):
        return None

    try:
        # 1. Query USN journal to get NextUsn
        out_buf = ctypes.create_string_buffer(56)
        bytes_returned = ctypes.c_ulong()

        success = ctypes.windll.kernel32.DeviceIoControl(
            h_volume,
            FSCTL_QUERY_USN_JOURNAL,
            None,
            0,
            out_buf,
            len(out_buf),
            ctypes.byref(bytes_returned),
            None,
        )
        if not success:
            return None

        # Unpack NextUsn (int64 at offset 16)
        _, _, next_usn = struct.unpack("<Qqq", out_buf.raw[:24])

        # 2. Enumerate USN data records
        buf_size = 65536
        enum_buf = ctypes.create_string_buffer(buf_size)
        start_frn = 0
        nodes = {}

        while True:
            # MFT_ENUM_DATA_V0 structure: StartFileReferenceNumber (8B), LowUsn (8B), HighUsn (8B)
            in_buf = struct.pack("<QQQ", start_frn, 0, next_usn)

            success = ctypes.windll.kernel32.DeviceIoControl(
                h_volume,
                FSCTL_ENUM_USN_DATA,
                in_buf,
                len(in_buf),
                enum_buf,
                buf_size,
                ctypes.byref(bytes_returned),
                None,
            )

            if not success:
                err = ctypes.GetLastError()
                # ERROR_HANDLE_EOF (38) is returned when enumeration is done
                if err == 38:
                    break
                return None

            bytes_read = bytes_returned.value
            if bytes_read < 8:
                break

            # The first 8 bytes of the output buffer contain the next StartFileReferenceNumber
            start_frn = struct.unpack("<Q", enum_buf.raw[:8])[0]

            offset = 8
            while offset < bytes_read:
                if offset + 4 > bytes_read:
                    break

                record_len = struct.unpack("<I", enum_buf.raw[offset : offset + 4])[0]
                if record_len == 0 or offset + record_len > bytes_read:
                    break

                # Unpack USN_RECORD_V2 header
                record_data = enum_buf.raw[offset : offset + 60]
                if len(record_data) < 60:
                    break

                fields = struct.unpack("<IHHQQqqIIIIHH", record_data)
                major = fields[1]
                if major != 2:
                    # Skip non-V2 records
                    offset += record_len
                    continue

                frn = fields[3]
                parent_frn = fields[4]
                attributes = fields[10]
                name_len = fields[11]
                name_offset = fields[12]

                name_start = offset + name_offset
                name_end = name_start + name_len

                if name_end <= offset + record_len:
                    name_bytes = enum_buf.raw[name_start:name_end]
                    try:
                        name = name_bytes.decode("utf-16-le")
                    except Exception:
                        name = ""

                    if name:
                        is_dir = bool(attributes & 0x10)  # FILE_ATTRIBUTE_DIRECTORY
                        nodes[get_mft_index(frn)] = (name, get_mft_index(parent_frn), is_dir)

                offset += record_len

        # 3. Reconstruct paths from root
        resolved_paths = {}
        search_root_str = str(search_root.resolve()).lower().rstrip("\\")
        volume_prefix = f"{volume_letter.upper()}:\\"

        def resolve(mft_idx: int) -> str | None:
            if mft_idx in resolved_paths:
                return resolved_paths[mft_idx]

            if mft_idx == MFT_ROOT_INDEX:
                resolved_paths[mft_idx] = volume_prefix
                return volume_prefix

            node = nodes.get(mft_idx)
            if not node:
                return None

            name, parent_idx, _ = node
            parent_path = resolve(parent_idx)
            if not parent_path:
                return None

            res = (
                parent_path + "\\" + name if not parent_path.endswith("\\") else parent_path + name
            )
            resolved_paths[mft_idx] = res
            return res

        candidates = []
        for mft_idx in nodes:
            path_str = resolve(mft_idx)
            if path_str:
                path_str_lower = path_str.lower()
                # Check if descendant of search root
                if path_str_lower.startswith(search_root_str) and len(path_str_lower) > len(
                    search_root_str
                ):
                    candidates.append(Path(path_str))

        return candidates

    finally:
        if not is_invalid_handle(h_volume):
            ctypes.windll.kernel32.CloseHandle(h_volume)
