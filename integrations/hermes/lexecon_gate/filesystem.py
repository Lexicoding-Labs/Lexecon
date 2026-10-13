"""Descriptor-relative local workspace access; no symlink resolution or shell calls."""

import os
import stat
from contextlib import contextmanager
from pathlib import Path


class GateError(Exception):
    """An intentionally content-free failure code safe for model output and audit."""


MAX_BYTES = 32 * 1024
EXTENSIONS = {".txt", ".md", ".csv", ".rst"}
DENIED_PARTS = {"node_modules", "venv", "__pycache__", "dist", "build", "logs"}
SENSITIVE = ("secret", "credential", "password", "token", "session", "private_key", "id_rsa", "id_ed25519", "auth")


def absolute_path(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise GateError("absolute_path_required")
    return path


@contextmanager
def open_directory(path):
    """Walk from /, refusing symlinks in every ancestor (including /tmp aliases)."""
    path = absolute_path(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


@contextmanager
def open_private_file(path, *, append=False):
    path = absolute_path(path)
    with open_directory(path.parent) as parent:
        info = os.fstat(parent)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise GateError("private_parent_requires_0700")
        flags = os.O_NOFOLLOW | os.O_NONBLOCK
        flags |= (os.O_WRONLY | os.O_APPEND | os.O_CREAT) if append else os.O_RDONLY
        # Concurrent first writers can observe ENOENT from O_CREAT|O_NOFOLLOW
        # on macOS. Retry creation once through the same anchored directory fd.
        try:
            fd = os.open(path.name, flags, 0o600, dir_fd=parent)
        except FileNotFoundError:
            if not append:
                raise
            fd = os.open(path.name, flags, 0o600, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise GateError("private_file_requires_owner_0600")
            yield fd
        finally:
            os.close(fd)


def allowed_part(part):
    lower = part.lower()
    return (bool(part) and not part.startswith(".") and lower not in DENIED_PARTS
            and not any(word in lower for word in SENSITIVE)
            and not any(ord(char) < 32 or ord(char) == 127 for char in part))


def relative_path(value, *, listing=False):
    if listing and value == ".":
        return "."
    if not isinstance(value, str) or len(value) > 1024 or "\\" in value:
        raise GateError("invalid_path")
    parts = value.split("/")
    if not all(allowed_part(part) for part in parts):
        raise GateError("path_not_allowed")
    if not listing and Path(value).suffix.lower() not in EXTENSIONS:
        raise GateError("unsupported_file_type")
    return "/".join(parts)


@contextmanager
def open_relative(root_fd, path, *, directory=False):
    fd = os.dup(root_fd)
    try:
        parts = [] if path == "." else path.split("/")
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if directory or index < len(parts) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def list_files(root_fd, path):
    entries = []
    with open_relative(root_fd, path, directory=True) as fd, os.scandir(fd) as iterator:
        for count, entry in enumerate(iterator):
            if count >= 512:
                raise GateError("directory_too_large")
            if not allowed_part(entry.name) or entry.is_symlink():
                continue
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                entries.append({"name": entry.name, "type": "directory"})
            elif (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                  and Path(entry.name).suffix.lower() in EXTENSIONS and info.st_size <= MAX_BYTES):
                entries.append({"name": entry.name, "type": "file"})
    return {"entries": sorted(entries, key=lambda entry: entry["name"])}


def read_file(root_fd, path):
    with open_relative(root_fd, path) as fd:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_BYTES:
            raise GateError("file_not_allowed")
        chunks = bytearray()
        while len(chunks) <= MAX_BYTES:
            chunk = os.read(fd, min(4096, MAX_BYTES + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
        after = os.fstat(fd)
        if len(chunks) > MAX_BYTES or (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise GateError("file_changed_or_too_large")
        content = bytes(chunks).decode("utf-8")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in content):
            raise GateError("not_plain_text")
        return {"content": content}
