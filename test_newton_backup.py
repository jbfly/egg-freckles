import importlib.util
import socket
import struct
import threading

import pytest

from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "newton_backup", Path(__file__).parent / "runtime" / "newton_backup.py"
)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


def test_packet_and_nsof_round_trip():
    left, right = socket.socketpair()
    try:
        left.sendall(backup.packet(b"test", b"abc"))
        assert backup.receive(right) == (b"test", b"abc")
    finally:
        left.close()
        right.close()

    value = [{"name": "Internal", "kind": "store", "signature": 1234}]
    encoded = backup.nsof_root(value)
    assert backup.nsof_decode(encoded) == (value, len(encoded))

    large = b"\x02\x0c\x07\x03pkg\x00" + struct.pack(">IIII", 8, 0, 0, 0) + b"package0"
    decoded, offset = backup.nsof_decode(large)
    assert decoded["$large_binary"] == {
        "compressed": False, "size": 8, "compander": "", "params": "",
    }
    assert offset == len(large)


def test_dante_session_setup_uses_protocol_10_and_authenticates(monkeypatch):
    client, newton = socket.socketpair()
    desktop_challenge = bytes.fromhex("0123456789abcdef")
    newton_challenge = bytes.fromhex("fedcba9876543210")
    key = bytes.fromhex("f207bf4f851b167d")
    commands = []
    monkeypatch.setattr(backup.os, "urandom", lambda length: desktop_challenge)

    def fake_newton():
        try:
            newton.sendall(backup.packet(b"rtdk", struct.pack(">I", 9)))
            command, data = backup.receive(newton)
            commands.append(command)
            assert data == struct.pack(">I", 1)
            newton.sendall(backup.packet(b"name", b"Newton"))

            command, data = backup.receive(newton)
            commands.append(command)
            assert struct.unpack(">IIIIII", data[:24]) == (
                10, 1, 0x01234567, 0x89ABCDEF, 1, 1
            )
            apps, _ = backup.nsof_decode(data, 24)
            assert apps[0]["name"] == "Newton Harness"
            newton.sendall(backup.packet(
                b"ninf", struct.pack(">I", 10) + newton_challenge
            ))

            command, data = backup.receive(newton)
            commands.append(command)
            assert data == struct.pack(">I", 1)
            newton.sendall(backup.packet(b"dres", struct.pack(">i", 0)))

            command, data = backup.receive(newton)
            commands.append(command)
            assert data == struct.pack(">I", 90)
            newton.sendall(backup.packet(
                b"pass", backup.newton_encrypt(key, desktop_challenge)
            ))
            command, data = backup.receive(newton)
            commands.append(command)
            assert data == backup.newton_encrypt(key, newton_challenge)
        finally:
            newton.close()

    thread = threading.Thread(target=fake_newton)
    thread.start()
    backup.setup_session(client, 90)
    client.close()
    thread.join()

    assert backup.newton_password_key() == key
    assert backup.newton_encrypt(key, desktop_challenge).hex() == "7cbe6fb757f31ac1"
    assert commands == [b"dock", b"dinf", b"wicn", b"stim", b"pass"]


def test_synthetic_read_only_enumeration_sends_no_dump(tmp_path):
    client, newton = socket.socketpair()
    commands = []

    stores = [{
        "name": "Internal", "kind": "store", "signature": 1234,
        "totalsize": 4096, "usedsize": 1024,
    }]
    soups = ["Notes", "SystemInformation"]
    signatures = [11, 22]

    def fake_newton():
        try:
            expected = [b"gsto", b"ssto", b"gets", b"ssou", b"gids", b"ssou", b"gids"]
            for command in expected:
                actual, data = backup.receive(newton)
                commands.append(actual)
                assert actual == command
                if command == b"gsto":
                    newton.sendall(backup.packet(b"stor", backup.nsof_root(stores)))
                elif command in (b"ssto", b"ssou"):
                    newton.sendall(backup.packet(b"dres", struct.pack(">i", 0)))
                elif command == b"gets":
                    newton.sendall(backup.packet(
                        b"soup", backup.nsof_root(soups) + backup.nsof_root(signatures)
                    ))
                else:
                    count = 2 if len(commands) == 5 else 0
                    ids = [101, 102][:count]
                    newton.sendall(backup.packet(
                        b"sids", struct.pack(">I", count) + b"".join(struct.pack(">I", i) for i in ids)
                    ))
        finally:
            newton.close()

    thread = threading.Thread(target=fake_newton)
    thread.start()
    manifest = backup.enumerate_and_dump(client)
    client.close()
    thread.join()

    assert commands == [b"gsto", b"ssto", b"gets", b"ssou", b"gids", b"ssou", b"gids"]
    assert [soup["entry_count"] for soup in manifest["stores"][0]["soups"]] == [2, 0]
    assert not list(tmp_path.iterdir())


def test_synthetic_dump_preserves_raw_entry(tmp_path):
    client, newton = socket.socketpair()
    entry = backup.nsof_root({"_uniqueID": 42, "text": "bootstrap"})

    def fake_newton():
        try:
            replies = {
                b"gsto": (b"stor", backup.nsof_root([
                    {"name": "Internal", "kind": "store", "signature": 1}
                ])),
                b"ssto": (b"dres", struct.pack(">i", 0)),
                b"gets": (b"soup", backup.nsof_root(["Notes"]) + backup.nsof_root([7])),
                b"ssou": (b"dres", struct.pack(">i", 0)),
                b"gids": (b"sids", struct.pack(">II", 1, 42)),
            }
            for expected in (b"gsto", b"ssto", b"gets", b"ssou", b"gids", b"rete"):
                command, data = backup.receive(newton)
                assert command == expected
                if command == b"rete":
                    assert data == struct.pack(">I", 42)
                    newton.sendall(backup.packet(b"entr", entry))
                else:
                    reply, data = replies[command]
                    newton.sendall(backup.packet(reply, data))
        finally:
            newton.close()

    thread = threading.Thread(target=fake_newton)
    thread.start()
    output = tmp_path / "export"
    backup.enumerate_and_dump(client, output)
    client.close()
    thread.join()

    assert (output / "01-Internal" / "01-Notes" / "000001.nsof").read_bytes() == entry
    assert "bootstrap" in (output / "01-Internal" / "01-Notes" / "000001.json").read_text()
    assert (output / "manifest.json").is_file()


def test_dump_refuses_existing_directory(tmp_path):
    left, right = socket.socketpair()
    try:
        with pytest.raises(ValueError, match="already exists"):
            backup.enumerate_and_dump(left, tmp_path)
    finally:
        left.close()
        right.close()


def test_dump_resume_skips_sequential_entries(tmp_path):
    client, newton = socket.socketpair()
    output = tmp_path / "partial"
    directory = output / "01-Internal" / "01-Notes"
    directory.mkdir(parents=True)
    first = backup.nsof_root({"_uniqueID": 41})
    second = backup.nsof_root({"_uniqueID": 42})
    (directory / "000001.nsof").write_bytes(first)

    def fake_newton():
        try:
            replies = {
                b"gsto": (b"stor", backup.nsof_root([
                    {"name": "Internal", "kind": "store", "signature": 1}
                ])),
                b"ssto": (b"dres", struct.pack(">i", 0)),
                b"gets": (b"soup", backup.nsof_root(["Notes"]) + backup.nsof_root([7])),
                b"ssou": (b"dres", struct.pack(">i", 0)),
                b"gids": (b"sids", struct.pack(">III", 2, 41, 42)),
            }
            for expected in (b"gsto", b"ssto", b"gets", b"ssou", b"gids", b"rete"):
                command, data = backup.receive(newton)
                assert command == expected
                if command == b"rete":
                    assert data == struct.pack(">I", 42)
                    newton.sendall(backup.packet(b"entr", second))
                else:
                    reply, body = replies[command]
                    newton.sendall(backup.packet(reply, body))
        finally:
            newton.close()

    thread = threading.Thread(target=fake_newton)
    thread.start()
    backup.enumerate_and_dump(client, output, resume=True)
    client.close()
    thread.join()

    assert (directory / "000001.nsof").read_bytes() == first
    assert (directory / "000002.nsof").read_bytes() == second
    assert (output / "manifest.json").is_file()
