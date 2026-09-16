#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="${project_dir}/.venv"

python3 -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install --upgrade pip
"${venv_dir}/bin/python" -m pip install -e "${project_dir}"

printf '\nInstalacion lista. Active el entorno con:\n  source %s/bin/activate\n' "${venv_dir}"
printf 'Prueba rapida:\n  fototriage --help\n'

