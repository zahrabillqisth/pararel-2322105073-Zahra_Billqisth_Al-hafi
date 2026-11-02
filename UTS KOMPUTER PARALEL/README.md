# paralel-[NIM]-[Nama]

**UTS Komputer Paralel (Sistem Terdistribusi) - Opsi B: Image Convolution / Blur Filter**
Universitas Cendekia Abditama - Teknik Informatika - TA 2026/2027

Satu masalah (konvolusi citra grayscale PGM, minimal 2000x2000) diselesaikan dengan dua pendekatan paralel
**POSIX Threads (Pthreads)** dan **OpenMP**, dibandingkan terhadap versi serial.

* Filter: **Gaussian blur 5x5** dan **Sobel 3x3** (edge detection)
* Border: **zero-padding** atau **replicate** (clamp)
* I/O: PGM P5/P2 dengan parser sendiri (tanpa library citra)
* Hasil paralel identik **byte-per-byte** dengan versi serial (aritmetika integer)

## Struktur

```
src/filter.[ch]        inti konvolusi, border, versi serial
src/par_pthreads.c     paralelisasi eksplisit (POSIX Threads)
src/par_openmp.c       paralelisasi dengan #pragma omp parallel for
src/pgm.c              baca/tulis PGM
src/main.c             driver CLI + pengukur waktu (baca / komputasi / tulis)
tools/gen_pgm.c        pembangkit citra uji sintetis (seed tetap 42)
tools/pgmcmp.c         pembanding dua PGM byte-per-byte
tools/make_report.py   pembuat laporan PDF dari hasil pengukuran
tests/test_correct.c   tes manual + tes acak vs referensi naif
scripts/bench.sh       benchmark otomatis -> results/results.csv
report/                laporan PDF
```

## Kebutuhan

`gcc` (dengan OpenMP), `make`, Linux/macOS/WSL. Untuk laporan: `python3` + `matplotlib`, `reportlab`, `pypdf`, `Pillow`.

## Compile

```bash
make            # membangun bin/conv, bin/gen_pgm, bin/pgmcmp
make clean
```

## Menjalankan

```bash
make data       # buat data/input_2000.pgm (2000x2000)

# pemakaian: conv -i in.pgm -o out.pgm [-m serial|pthreads|openmp] [-t N]
#                 [-f gaussian|sobel] [-b zero|replicate] [-r REPEAT] [--csv]
./bin/conv -i data/input_2000.pgm -o out/serial.pgm  -m serial   -f gaussian -b replicate
./bin/conv -i data/input_2000.pgm -o out/pth.pgm     -m pthreads -t 4 -f gaussian -b replicate
./bin/conv -i data/input_2000.pgm -o out/omp.pgm     -m openmp   -t 4 -f gaussian -b replicate

./bin/pgmcmp out/serial.pgm out/pth.pgm     # harus: IDENTIK
```

Program dapat dipakai dengan PGM milik sendiri (P5 atau P2, maxval <= 255).

## Verifikasi correctness

```bash
make test       # tes manual (nilai hitung tangan) + tes acak vs referensi naif, 1..16 thread
```

## Benchmark dan laporan

```bash
make bench                              # SIZES="2000" REPEATS=10 THREADS="1 2 4 8" (bisa di-override)
make report NIM=123456 NAMA="Nama Anda" # -> report/Laporan_UTS_Paralel.pdf
```

> **Penting:** angka di `results/` dan di PDF yang disertakan awalnya dibuat pada mesin dengan **1 core**,
> sehingga speedup tidak dapat melebihi 1x. Jalankan `make bench && make report NIM=... NAMA="..."`
> pada **mesin multi-core Anda** (>= 8 core untuk kurva penuh) agar grafik speedup/efficiency mencerminkan
> perangkat keras Anda. Narasi analisis di laporan menyesuaikan otomatis dengan data baru.

## Mengumpulkan ke GitHub

Nama repository wajib `paralel-[NIM]-[Nama]` dan **public**:

```bash
mv paralel-NIM-Nama paralel-123456-NamaAnda      # sesuaikan
cd paralel-123456-NamaAnda
git init && git add . && git commit -m "UTS Komputer Paralel - Opsi B"
git branch -M main
git remote add origin https://github.com/<username>/paralel-123456-NamaAnda.git
git push -u origin main
```
