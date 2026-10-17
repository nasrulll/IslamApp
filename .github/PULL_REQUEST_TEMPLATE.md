## Ringkasan

## Keamanan repository public
- [ ] Tidak ada secret, korpus, data pihak ketiga, atau dokumen internal
- [ ] Pesan commit dan nama branch tidak menyebut sumber data
- [ ] `python -m tools.repo_visibility_guard --visibility public --history` lulus
- [ ] Workflow baru: `permissions:` minimal dan action pihak ketiga di-pin ke SHA

## Pengujian
