from __future__ import annotations

import socket

import start


def test_port_check_reports_listener_without_terminating_it() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    try:
        assert start.check_port_available(port) is False

        client = socket.create_connection(("127.0.0.1", port), timeout=1)
        connection, _ = listener.accept()
        connection.close()
        client.close()
    finally:
        listener.close()
