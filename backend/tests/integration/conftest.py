import os
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator

import pytest

POSTGRES_IMAGE = "postgres:17.9-bookworm"


@pytest.fixture
def postgres_url() -> Iterator[str]:
    host = _docker_host_gateway()
    port = _host_port()
    name = f"harbor-postgres-{os.getpid()}-{uuid.uuid4().hex[:12]}"

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"0.0.0.0:{port}:5432",
            "-e",
            "POSTGRES_USER=postgres",
            "-e",
            "POSTGRES_PASSWORD=postgres",
            "-e",
            "POSTGRES_DB=test",
            POSTGRES_IMAGE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    try:
        _wait_for_postgres(host, port)
        yield f"postgresql+asyncpg://postgres:postgres@{host}:{port}/test"
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True, text=True)


def _wait_for_postgres(host: str, port: int) -> None:
    for _ in range(60):
        result = subprocess.run(
            ["pg_isready", "-h", host, "-p", str(port), "-U", "postgres", "-d", "test"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)

    msg = f"Postgres did not become ready on {host}:{port}"
    raise RuntimeError(msg)


def _host_port() -> int:
    base = 30_000 + (os.getpid() % 10_000)
    for port in range(base, base + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    msg = "could not reserve a host port for Postgres"
    raise RuntimeError(msg)


def _docker_host_gateway() -> str:
    with open("/proc/net/route", encoding="utf-8") as routes:
        for line in routes.readlines()[1:]:
            fields = line.split()
            if len(fields) >= 3 and fields[1] == "00000000":
                raw = int(fields[2], 16)
                return ".".join(str((raw >> shift) & 0xFF) for shift in (0, 8, 16, 24))
    return "127.0.0.1"
