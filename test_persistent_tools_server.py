import socket
import threading
import unittest

from runtime.persistent_tools_server import PersistentTools, unescape


class PersistentToolsTest(unittest.TestCase):
    def test_round_trip_reuses_connection(self) -> None:
        host, newton = socket.socketpair()
        tools = PersistentTools()
        tools.attach(host)

        def device() -> None:
            stream = newton.makefile("rb")
            for expected_id in ("1", "2"):
                request = stream.readline().decode().split()
                self.assertEqual(request[:3], ["TOOLS", expected_id, "ping"])
                newton.sendall(f"{expected_id}\r\nresult\r\npong\r\n".encode())
            stream.close()
            newton.close()

        thread = threading.Thread(target=device)
        thread.start()
        self.assertEqual(tools.submit("ping", {}, 1)["result"], "pong")
        self.assertEqual(tools.submit("ping", {}, 1)["request_id"], "2")
        thread.join()
        tools.detach(host)

    def test_timeout_keeps_connection_attached(self) -> None:
        host, newton = socket.socketpair()
        tools = PersistentTools()
        tools.attach(host)
        with self.assertRaises(TimeoutError):
            tools.submit("ping", {}, 0.01)
        self.assertIs(tools.connection, host)
        tools.detach(host)
        newton.close()

    def test_unescape(self) -> None:
        self.assertEqual(unescape(r"one\ntwo\\three"), "one\ntwo\\three")


if __name__ == "__main__":
    unittest.main()
