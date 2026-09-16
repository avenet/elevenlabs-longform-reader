# Long-form Reading Service

Turn long text into spoken audio with ElevenLabs. Paste text or upload a `.txt` / `.pdf`, wait while sections generate in the background, then listen in the built-in player. Generated MP3 files are cached on local disk.

## Requirements

- Python 3.14+
- [Pipenv](https://pipenv.pypa.io/)
- An [ElevenLabs](https://elevenlabs.io/) API key

## Setup

```bash
cd eleven-labs-demo
PIPENV_VENV_IN_PROJECT=1 pipenv install
cp .env.example .env
```

Edit `.env` and set your key:

```
ELEVENLABS_API_KEY=your_real_key
```

Optional settings:

- `ELEVENLABS_VOICE_ID` — default voice
- `ELEVENLABS_MODEL_ID` — default model (`eleven_multilingual_v2`)
- `MEDIA_ROOT` — where MP3 files are stored (default `./media/audio`)
- `DATABASE_URL` — SQLite database path (default `sqlite:///./data/readings.db`)

## Run

```bash
pipenv run serve
# or: make serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

API docs are available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Common shortcuts (`pipenv run …` or `make …`):

| Command | What it does |
|---------|----------------|
| `serve` | Start uvicorn with reload |
| `lint` | Ruff check |
| `fmt` | Ruff format |
| `lint-fixup` | Ruff check with autofix |
| `test` | Full pytest suite |
| `test-unit` | Pytest without live ElevenLabs |
| `test-live` | Live ElevenLabs integration tests |
| `check` | Lint + mocked tests |
| `cov` | Mocked tests with coverage report |
| `install-hooks` | Install git pre-commit (runs `fmt`, `lint`, `test`) |
| `make help` | List Makefile targets |

After cloning, run `make install-hooks` once so every commit runs `make fmt`, `make lint`, and `make test`.

## Usage

1. Paste text or choose a `.txt` / `.pdf` file.
2. Pick a voice and submit.
3. The app splits the document into listening-sized sections and generates speech asynchronously.
4. Playback starts when the first section is ready; later sections keep generating in the background.

Audio files live under `media/audio/` (per-reading folders plus a shared `_cache/` for identical section reuse). Metadata is stored in SQLite under `data/`.

## API overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/readings` | Create a reading from `text` or uploaded `file` |
| `GET` | `/api/readings/{id}` | Reading status and sections |
| `GET` | `/api/readings/{id}/sections/{index}/audio` | Stream a ready MP3 section |
| `GET` | `/api/voices` | List available ElevenLabs voices |
