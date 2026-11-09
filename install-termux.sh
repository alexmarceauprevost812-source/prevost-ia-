#!/data/data/com.termux/files/usr/bin/bash
set -eu

if [ -z "${PREFIX:-}" ] || ! command -v pkg >/dev/null 2>&1; then
    echo 'Cet installateur doit être lancé dans Termux : bash install-termux.sh' >&2
    exit 1
fi

prevost_source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
echo 'Installation de Python et du chiffrement depuis les paquets Termux.'
pkg install python python-cryptography
python "$prevost_source_dir/integration/install_launcher.py" --bin-dir "$PREFIX/bin"
echo 'PRÉVOST v2 prêt : prevost --project DOSSIER ; prevost coffre ; prevost reseau appareils'
echo 'Conserver le dépôt à cet emplacement. Aucun scan ni modèle téléchargé.'
