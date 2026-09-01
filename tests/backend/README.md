# Backend tests

Testing the backends with docker and validating via the `BackendStats`. Also validates the data was written by reading it back

## Running locally


```sh
docker compose -f tests/backend/docker-compose.yml up -d
uv run pytest -m backend
docker compose -f tests/backend/docker-compose.yml down -v
```

socket, ZMQ and HTTP tests do not need docker

```sh
uv run pytest tests/backend/test_socket.py tests/backend/test_zmq.py tests/backend/test_http.py
```
