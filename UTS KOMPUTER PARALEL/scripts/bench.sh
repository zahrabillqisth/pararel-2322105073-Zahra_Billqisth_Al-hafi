#!/usr/bin/env bash
# bench.sh - Sweep benchmark: filter x border x mode x jumlah thread.
# Output: results/results.csv, results/sysinfo.txt
# Variabel lingkungan: SIZES="2000" REPEATS=10 THREADS="1 2 4 8"
set -euo pipefail
cd "$(dirname "$0")/.."
SIZES=${SIZES:-"2000"}; REPEATS=${REPEATS:-10}; THREADS=${THREADS:-"1 2 4 8"}
mkdir -p results out data bin

{
  echo "nproc=$(nproc)"
  echo "cpu=$(lscpu 2>/dev/null | awk -F: "/Model name/ {gsub(/^ +/,\"\",\$2); print \$2; exit}")"
  echo "gcc=$(${CC:-gcc} --version | head -1)"
  echo "kernel=$(uname -sr)"
  echo "repeats=$REPEATS"
} > results/sysinfo.txt

echo "size,filter,border,mode,threads,read_ms,compute_ms,compute_min_ms,write_ms,correct" > results/results.csv

for size in $SIZES; do
  img="data/input_${size}.pgm"
  [ -f "$img" ] || ./bin/gen_pgm -w "$size" -h "$size" -o "$img"
  for f in gaussian sobel; do
    for b in replicate zero; do
      echo ">> size=$size filter=$f border=$b"
      ./bin/conv -i "$img" -o out/serial.pgm -m serial -f $f -b $b -r "$REPEATS" --csv | sed "s/\$/,1/" >> results/results.csv
      for mode in pthreads openmp; do
        for t in $THREADS; do
          row=$(./bin/conv -i "$img" -o out/tmp.pgm -m $mode -t $t -f $f -b $b -r "$REPEATS" --csv)
          if ./bin/pgmcmp out/serial.pgm out/tmp.pgm >/dev/null; then ok=1; else ok=0; fi
          echo "$row,$ok" >> results/results.csv
        done
      done
    done
  done
done
echo "Selesai -> results/results.csv"
