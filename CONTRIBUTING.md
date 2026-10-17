# Kontribusi

Repository ini **public**. Semua yang di-push (commit, branch, PR, issue, komentar, log Actions) langsung terbaca publik dan dapat di-fork selamanya. Menghapusnya kemudian tidak menghapus salinan yang sudah ada.

## Jangan pernah menambahkan
- Token, kata sandi, kunci, atau file `.env`.
- Korpus, teks kitab, basis data, ekspor, atau data pihak ketiga (PDF, EPUB, CSV, JSONL, Parquet, SQLite, arsip).
- Nama atau lokasi hosting dataset sumber, atau akun pemiliknya. Ini berlaku juga untuk pesan commit, nama branch, issue, PR, dan komentar.
- Dokumen strategi, bisnis, atau arsitektur data yang belum sengaja diputuskan untuk dibuka.

Tidak yakin apakah sesuatu boleh publik? Anggap tidak boleh.

## Pengaturan sekali
```bash
git config core.hooksPath .githooks
```
Hook `pre-push` memakai aturan public dan memeriksa isi file, seluruh riwayat, pesan commit, dan nama branch sebelum push.

## Alur kerja
1. Buat branch dengan nama netral yang menjelaskan kodenya, lalu buka PR. Jangan push langsung ke `main`.
2. Pesan commit menjelaskan perubahan kode saja.
3. Check `guard` harus hijau sebelum merge.
4. Periksa manual sebelum push: `python -m tools.repo_visibility_guard --visibility public --history`.

## Workflow GitHub Actions
- Wajib `permissions:` tingkat atas yang minimal; tanpa `write-all`.
- Action pihak ketiga di-pin ke SHA commit 40 karakter.
- Tanpa trigger `pull_request_target` atau `workflow_run`.
- Workflow yang memakai secret hanya boleh berjalan pada `push`, `workflow_dispatch`, atau `schedule`.
- Jangan unggah artefak kecuali sudah ditinjau; artefak repo public dapat diunduh siapa saja.
