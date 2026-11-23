#!/usr/bin/env bash
# Crea los archivos de prueba: JPEG de 5 MB, 100 KB y 11 MB (cabecera JPEG real + bytes aleatorios) y un ejecutable disfrazado.
set -euo pipefail
DIR="${1:-/opt/poc/datos}"; mkdir -p "$DIR"
jpeg() { { printf '\xff\xd8\xff\xe0'; head -c $(( $2 - 4 )) /dev/urandom; } > "$DIR/$1"; }
jpeg evidencia_5mb.jpg 5242880
jpeg evidencia_100kb.jpg 102400
jpeg evidencia_11mb.jpg 11534336
{ printf 'MZ\x90\x00'; head -c 102396 /dev/urandom; } > "$DIR/ejecutable_disfrazado.jpg"
ls -l "$DIR"
