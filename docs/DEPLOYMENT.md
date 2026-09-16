# Deployment

## Local Python

Use Python 3.13, create a virtual environment and install `requirements-dev.txt`
for development or `requirements.txt` for runtime. Copy `.env.example` to `.env`
and configure credentials. Run the API and worker in separate terminals using
the same database path:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.worker
```

Open `http://127.0.0.1:8000/dashboard`; API documentation is at `/docs`.

## Docker Compose (one host)

1. Install Docker Engine/Desktop with Compose.
2. Configure `.env` and create `secrets/`. For app mode put the PEM at
   `secrets/github-app.pem`; make it readable by container UID 10001.
3. Run `docker compose up --build -d`.
4. Check `docker compose ps`, `docker compose logs worker` and `/health`.

The API and worker share one persistent named volume. Both run without root,
with a read-only root filesystem and a writable `/data` volume. Port 8000 binds
to localhost by default. Put a reverse proxy with HTTPS in front of it before
configuring a public GitHub webhook. Keep dashboard access token protected.

`/health` is process liveness, not a claim that GitHub/Groq credentials work or
that a worker is consuming jobs. Monitor queued-job age and worker logs. Verify
one real PR after deployment. Never use `docker compose down -v` unless you
intend to remove persisted review history.

For Railway or another host, deploy API and worker together on a service/host
that genuinely shares the same local persistent volume. Separate replicas with
independent disks will not work with this SQLite architecture. Use PostgreSQL
and distributed coordination before scaling to multiple hosts.

## CI

GitHub Actions checks lint, formatting, coverage (minimum 80%), tests, the
offline evaluation harness, and the container health endpoint. It requires no
GitHub/Groq secrets and never posts review comments. The live model benchmark is
explicitly run outside CI. CI runs only after these local commits are pushed.

References: [Docker Compose service configuration](https://docs.docker.com/reference/compose-file/services/),
[GitHub Python CI](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
