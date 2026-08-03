#!/usr/bin/env python3
"""Read Newton stores/soups over the Dock protocol; optionally export entries."""

import argparse
import json
import os
import socket
import struct
import subprocess
import sys
from pathlib import Path

ADDRESS = "10.42.0.1"
PORT = 3679
HEADER = b"newtdock"
MAX_PACKET = 64 * 1024 * 1024
PROTOCOL_VERSION = 10


class Symbol(str):
    pass


def packet(command, data=b""):
    if len(command) != 4:
        raise ValueError("Dock commands are four bytes")
    return HEADER + command + struct.pack(">I", len(data)) + data + b"\0" * (-len(data) % 4)


def receive_exact(sock, length):
    data = bytearray()
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise RuntimeError("Newton disconnected during transfer")
        data.extend(chunk)
    return bytes(data)


def receive(sock):
    header = receive_exact(sock, 16)
    if header[:8] != HEADER:
        raise RuntimeError(f"bad Dock header: {header[:8]!r}")
    length = struct.unpack(">I", header[12:])[0]
    if length > MAX_PACKET:
        raise RuntimeError(f"unreasonable Dock packet length: {length}")
    data = receive_exact(sock, (length + 3) & ~3)[:length]
    return header[8:12], data


def expect(sock, expected):
    command, data = receive(sock)
    if command != expected:
        raise RuntimeError(
            f"expected {expected.decode()}, received {command.decode('ascii', 'replace')}"
        )
    return data


def expect_ok(sock, operation):
    data = expect(sock, b"dres")
    if len(data) < 4:
        raise RuntimeError(f"short result after {operation}")
    error = struct.unpack(">i", data[:4])[0]
    if error:
        raise RuntimeError(f"Newton rejected {operation} with Dock error {error}")


def xlong(value):
    return bytes([value]) if 0 <= value < 255 else b"\xff" + struct.pack(">i", value)


def nsof_encode(value):
    if value is None:
        return b"\x0a"
    if value is True:
        return b"\x00\x1a"
    if isinstance(value, int):
        return b"\x00" + xlong(value << 2)
    if isinstance(value, Symbol):
        raw = value.encode("ascii")
        return b"\x07" + xlong(len(raw)) + raw
    if isinstance(value, str):
        raw = value.encode("utf-16-be") + b"\0\0"
        return b"\x08" + xlong(len(raw)) + raw
    if isinstance(value, list):
        return b"\x05" + xlong(len(value)) + b"".join(nsof_encode(v) for v in value)
    if isinstance(value, dict):
        keys = list(value)
        return (b"\x06" + xlong(len(keys))
                + b"".join(nsof_encode(Symbol(k)) for k in keys)
                + b"".join(nsof_encode(value[k]) for k in keys))
    raise TypeError(f"cannot encode NSOF value {type(value).__name__}")


def nsof_root(value):
    return b"\x02" + nsof_encode(value)


def _shift_newton_key(key):
    high, low = struct.unpack(">II", key)
    return struct.pack(">II", (high << 1) & 0xFFFFFFFF, (low << 1) & 0xFFFFFFFF)


def _des_block(key, data):
    if len(key) != 8 or len(data) != 8:
        raise ValueError("DES keys and blocks must be eight bytes")
    base = ["openssl", "enc", "-des-ecb", "-K", key.hex(), "-nosalt", "-nopad"]
    attempts = [base[:3] + ["-provider", "legacy"] + base[3:], base]
    error = "OpenSSL DES failed"
    for command in attempts:
        try:
            result = subprocess.run(command, input=data, capture_output=True)
        except FileNotFoundError:
            raise RuntimeError("OpenSSL is required for the Newton Dock password exchange") from None
        if result.returncode == 0 and len(result.stdout) == 8:
            return result.stdout
        error = result.stderr.decode("utf-8", "replace").strip() or error
    raise RuntimeError(f"OpenSSL DES failed: {error}")


def newton_password_key(password=""):
    units = list(struct.unpack(f">{len(password.encode('utf-16-be')) // 2}H",
                               password.encode("utf-16-be")))
    units.append(0)
    key = bytes.fromhex("57406860626d7464")
    offset = 0
    while True:
        block = units[offset:offset + 4]
        offset += len(block)
        ended = 0 in block
        block = block[:block.index(0)] if ended else block
        data = b"".join(struct.pack(">H", value) for value in block).ljust(8, b"\0")
        encrypted = _des_block(_shift_newton_key(key), data)
        fixed = bytearray()
        for value in encrypted:
            odd = (value & 0xFE) | ((value & 0xFE).bit_count() % 2 == 0)
            fixed.append(value | odd)  # Newton preserves a historical parity bug.
        key = bytes(fixed)
        if ended:
            return key


def newton_encrypt(key, challenge):
    return _des_block(_shift_newton_key(key), challenge)


def setup_session(sock, timeout, password=""):
    command, _ = receive(sock)
    if command not in (b"rtdk", b"auto"):
        raise RuntimeError(f"expected docking request, received {command!r}")
    sock.sendall(packet(b"dock", struct.pack(">I", 1)))
    expect(sock, b"name")

    desktop_challenge = os.urandom(8)
    app = [{"name": "Newton Harness", "id": 2, "version": 1, "doesAuto": True}]
    info = struct.pack(">IIIIII", PROTOCOL_VERSION, 1,
                       *struct.unpack(">II", desktop_challenge), 1, 1)
    sock.sendall(packet(b"dinf", info + nsof_root(app)))

    newton_info = expect(sock, b"ninf")
    if len(newton_info) < 12:
        raise RuntimeError("short Newton session information")
    version = struct.unpack(">I", newton_info[:4])[0]
    if version != PROTOCOL_VERSION:
        raise RuntimeError(f"Newton negotiated unsupported Dock protocol {version}")
    newton_challenge = newton_info[4:12]

    sock.sendall(packet(b"wicn", struct.pack(">I", 1)))
    expect_ok(sock, "Dock capability negotiation")
    sock.sendall(packet(b"stim", struct.pack(">I", int(timeout))))

    key = newton_password_key(password)
    response = expect(sock, b"pass")
    if response != newton_encrypt(key, desktop_challenge):
        raise RuntimeError("Newton rejected the configured Dock password")
    sock.sendall(packet(b"pass", newton_encrypt(key, newton_challenge)))


class NSOFDecoder:
    def __init__(self, data):
        self.data = data
        self.offset = 0
        self.precedents = []

    def take(self, count):
        end = self.offset + count
        if end > len(self.data):
            raise ValueError("truncated NSOF object")
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def xlong(self):
        first = self.take(1)[0]
        return first if first < 255 else struct.unpack(">i", self.take(4))[0]

    def object(self):
        tag = self.take(1)[0]
        if tag == 9:
            index = self.xlong()
            try:
                return self.precedents[index]
            except IndexError:
                raise ValueError(f"invalid NSOF precedent {index}") from None
        if tag == 0:
            value = self.xlong()
            if value == 0x1A:
                return True
            if value == 2:
                return None
            if value & 3 == 0:
                return value >> 2
            return {"$immediate": value}
        if tag == 10:
            return None
        if tag == 1:
            return chr(self.take(1)[0])
        if tag == 2:
            return chr(struct.unpack(">H", self.take(2))[0])

        precedent = len(self.precedents)
        self.precedents.append(None)
        if tag == 11:
            top, left, bottom, right = self.take(4)
            value = {"top": top, "left": left, "bottom": bottom, "right": right}
        elif tag == 7:
            value = Symbol(self.take(self.xlong()).decode("ascii"))
        elif tag == 8:
            raw = self.take(self.xlong())
            value = raw[:-2].decode("utf-16-be") if raw.endswith(b"\0\0") else raw.decode("utf-16-be")
        elif tag == 5:
            value = [self.object() for _ in range(self.xlong())]
        elif tag == 4:
            count = self.xlong()
            value = {"$class": self.object(), "$values": [self.object() for _ in range(count)]}
        elif tag == 6:
            count = self.xlong()
            keys = [self.object() for _ in range(count)]
            value = {str(key): self.object() for key in keys}
        elif tag == 3:
            length = self.xlong()
            value = {"$class": self.object(), "$binary": self.take(length).hex()}
        else:
            raise ValueError(f"unsupported NSOF tag {tag}")
        self.precedents[precedent] = value
        return value


def nsof_decode(data, offset=0):
    decoder = NSOFDecoder(data[offset:])
    if decoder.take(1) != b"\x02":
        raise ValueError("unsupported NSOF version")
    value = decoder.object()
    return value, offset + decoder.offset


def safe_name(value):
    text = "".join(c if c.isalnum() or c in "._-" else "_" for c in str(value)).strip("._")
    return text or "unnamed"


def stores_from(data):
    stores, _ = nsof_decode(data)
    if not isinstance(stores, list) or not all(isinstance(store, dict) for store in stores):
        raise ValueError("invalid store list")
    return stores


def soups_from(data):
    names, offset = nsof_decode(data)
    signatures, _ = nsof_decode(data, offset)
    if not isinstance(names, list) or not isinstance(signatures, list) or len(names) != len(signatures):
        raise ValueError("invalid soup list")
    return list(zip(names, signatures))


def soup_ids(data):
    if len(data) < 4:
        raise ValueError("short soup ID list")
    count = struct.unpack(">I", data[:4])[0]
    if len(data) < 4 + count * 4:
        raise ValueError("truncated soup ID list")
    return list(struct.unpack(f">{count}I", data[4:4 + count * 4]))


def select_store(sock, store):
    required = {key: store.get(key) for key in ("name", "kind", "signature")}
    if None in required.values():
        raise ValueError(f"store lacks name/kind/signature: {store!r}")
    sock.sendall(packet(b"ssto", nsof_root(required)))
    expect_ok(sock, f"selecting store {required['name']}")


def select_soup(sock, name):
    sock.sendall(packet(b"ssou", str(name).encode("utf-16-be") + b"\0\0"))
    expect_ok(sock, f"selecting soup {name}")


def enumerate_and_dump(sock, output=None, resume=False):
    if output is not None and output.exists() and not resume:
        raise ValueError(f"dump directory already exists: {output}")
    sock.sendall(packet(b"gsto"))
    stores = stores_from(expect(sock, b"stor"))
    manifest = {"format": "newton-dock-soup-export-v1", "stores": []}

    for store_index, store in enumerate(stores):
        select_store(sock, store)
        sock.sendall(packet(b"gets"))
        soups = soups_from(expect(sock, b"soup"))
        store_record = {key: store.get(key) for key in ("name", "kind", "signature", "totalsize", "usedsize")}
        store_record["soups"] = []
        manifest["stores"].append(store_record)
        print(f"Store {store_index + 1}: {store.get('name', '<unnamed>')} ({len(soups)} soups)")

        for soup_index, (name, signature) in enumerate(soups):
            select_soup(sock, name)
            sock.sendall(packet(b"gids"))
            ids = soup_ids(expect(sock, b"sids"))
            count = len(ids)
            soup_record = {"name": name, "signature": signature, "entry_count": count}
            store_record["soups"].append(soup_record)
            print(f"  {soup_index + 1:2}. {name}: {count} entries")
            if output is None:
                continue

            directory = output / f"{store_index + 1:02}-{safe_name(store.get('name'))}" / f"{soup_index + 1:02}-{safe_name(name)}"
            directory.mkdir(parents=True, exist_ok=True)
            existing = 0
            if resume:
                while (directory / f"{existing + 1:06}.nsof").is_file():
                    existing += 1
                if len(list(directory.glob("*.nsof"))) != existing or existing > count:
                    raise ValueError(f"cannot resume non-sequential soup export: {directory}")
            for written, entry_id in enumerate(ids[existing:], existing + 1):
                sock.sendall(packet(b"rete", struct.pack(">I", entry_id)))
                data = expect(sock, b"entr")
                (directory / f"{written:06}.nsof").write_bytes(data)
                try:
                    decoded, _ = nsof_decode(data)
                    (directory / f"{written:06}.json").write_text(
                        json.dumps(decoded, ensure_ascii=False, indent=2) + "\n"
                    )
                except (UnicodeError, ValueError):
                    pass
            written = len(ids)
            soup_record["entries_written"] = written
            if written != count:
                print(f"    warning: listed {count}, received {written}", file=sys.stderr)

    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(f"Soup export written to {output}")
    return manifest


def serve(address, port, timeout, output=None, password="", resume=False):
    with socket.create_server((address, port), reuse_port=False) as server:
        server.settimeout(timeout)
        print(f"Listening on {address}:{port}; now tap Connect in Dock on the Newton", flush=True)
        try:
            conn, peer = server.accept()
        except TimeoutError:
            raise RuntimeError(f"no Newton connected within {timeout:g}s") from None
        with conn:
            conn.settimeout(timeout)
            print(f"Newton connected from {peer[0]}:{peer[1]}", flush=True)
            setup_session(conn, timeout, password)
            try:
                return enumerate_and_dump(conn, output, resume)
            finally:
                try:
                    conn.sendall(packet(b"disc"))
                except OSError:
                    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default=os.environ.get("NEWTON_DOCK_ADDRESS", ADDRESS))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NEWTON_DOCK_PORT", PORT)))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("NEWTON_DOCK_TIMEOUT", "60")))
    parser.add_argument("--dump", metavar="DIRECTORY", type=Path,
                        help="export every soup entry; default only lists stores, soups, and counts")
    parser.add_argument("--password", default=os.environ.get("NEWTON_DOCK_PASSWORD", ""),
                        help="Dock connection password; default is empty")
    parser.add_argument("--resume", action="store_true",
                        help="continue a partial --dump directory without replacing files")
    args = parser.parse_args(argv)
    if args.resume and args.dump is None:
        parser.error("--resume requires --dump")
    serve(args.address, args.port, args.timeout, args.dump, args.password, args.resume)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"newton_backup.py: {error}", file=sys.stderr)
        sys.exit(1)
