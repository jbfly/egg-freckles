#!/usr/bin/env python3
"""Read Newton stores/soups over the Dock protocol; optionally export entries."""

import argparse
import json
import os
import socket
import struct
import sys
from pathlib import Path

ADDRESS = "10.42.0.1"
PORT = 3679
HEADER = b"newtdock"
MAX_PACKET = 64 * 1024 * 1024


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


def soup_count(data):
    if len(data) < 4:
        raise ValueError("short soup ID list")
    count = struct.unpack(">I", data[:4])[0]
    if len(data) < 4 + count * 4:
        raise ValueError("truncated soup ID list")
    return count


def select_store(sock, store):
    required = {key: store.get(key) for key in ("name", "kind", "signature")}
    if None in required.values():
        raise ValueError(f"store lacks name/kind/signature: {store!r}")
    sock.sendall(packet(b"ssto", nsof_root(required)))
    expect_ok(sock, f"selecting store {required['name']}")


def select_soup(sock, name):
    sock.sendall(packet(b"ssou", str(name).encode("utf-16-be") + b"\0\0"))
    expect_ok(sock, f"selecting soup {name}")


def enumerate_and_dump(sock, output=None):
    if output is not None and output.exists():
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
            count = soup_count(expect(sock, b"sids"))
            soup_record = {"name": name, "signature": signature, "entry_count": count}
            store_record["soups"].append(soup_record)
            print(f"  {soup_index + 1:2}. {name}: {count} entries")
            if output is None:
                continue

            directory = output / f"{store_index + 1:02}-{safe_name(store.get('name'))}" / f"{soup_index + 1:02}-{safe_name(name)}"
            directory.mkdir(parents=True, exist_ok=True)
            sock.sendall(packet(b"snds"))
            written = 0
            while True:
                command, data = receive(sock)
                if command == b"bsdn":
                    break
                if command != b"entr":
                    raise RuntimeError(f"expected soup entry, received {command!r}")
                written += 1
                (directory / f"{written:06}.nsof").write_bytes(data)
                try:
                    decoded, _ = nsof_decode(data)
                    (directory / f"{written:06}.json").write_text(
                        json.dumps(decoded, ensure_ascii=False, indent=2) + "\n"
                    )
                except (UnicodeError, ValueError):
                    pass
            soup_record["entries_written"] = written
            if written != count:
                print(f"    warning: listed {count}, received {written}", file=sys.stderr)

    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(f"Soup export written to {output}")
    return manifest


def serve(address, port, timeout, output=None):
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
            command, _ = receive(conn)
            if command not in (b"rtdk", b"auto"):
                raise RuntimeError(f"expected docking request, received {command!r}")
            conn.sendall(packet(b"dock", struct.pack(">I", 2)))
            expect(conn, b"name")
            conn.sendall(packet(b"stim", struct.pack(">I", int(timeout))))
            expect_ok(conn, "session setup")
            try:
                return enumerate_and_dump(conn, output)
            finally:
                conn.sendall(packet(b"disc"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default=os.environ.get("NEWTON_DOCK_ADDRESS", ADDRESS))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NEWTON_DOCK_PORT", PORT)))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("NEWTON_DOCK_TIMEOUT", "60")))
    parser.add_argument("--dump", metavar="DIRECTORY", type=Path,
                        help="export every soup entry; default only lists stores, soups, and counts")
    args = parser.parse_args(argv)
    serve(args.address, args.port, args.timeout, args.dump)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"newton_backup.py: {error}", file=sys.stderr)
        sys.exit(1)
