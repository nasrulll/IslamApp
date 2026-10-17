# Fikihmu

Kerangka awal aplikasi web dan API bootstrap yang **belum siap produksi**. Belum ada korpus, basis data, atau fitur AI.

## Menjalankan

- Web: `npm install`, lalu `npm run dev:web` (port 3000)
- API: `python -m pip install -r services/api/requirements-dev.txt`, lalu `python -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload`
- Cek mutu: `npm run lint && npm run typecheck && npm run build`; `python -m pytest tests/test_api_bootstrap.py`

## Pengaman repository

- Aktifkan hook lokal sekali: `git config core.hooksPath .githooks`
- Periksa sebelum push: `python -m tools.repo_visibility_guard --visibility public --history`

Jangan menambahkan korpus, kredensial, atau data pihak ketiga ke repository ini. Aturan lengkap: [CONTRIBUTING.md](CONTRIBUTING.md).
