# Makefile - Konvolusi citra paralel: Pthreads vs OpenMP
CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra -std=gnu11
LDLIBS  := -lm -lpthread
OMP     := -fopenmp
LIBSRC  := src/filter.c src/pgm.c src/par_pthreads.c src/par_openmp.c

.PHONY: all test data bench report loc clean

all: bin/conv bin/gen_pgm bin/pgmcmp

bin/conv: src/main.c $(LIBSRC) src/filter.h | bin
	$(CC) $(CFLAGS) $(OMP) -o $@ src/main.c $(LIBSRC) $(LDLIBS)

bin/gen_pgm: tools/gen_pgm.c src/pgm.c src/filter.h | bin
	$(CC) $(CFLAGS) -o $@ tools/gen_pgm.c src/pgm.c $(LDLIBS)

bin/pgmcmp: tools/pgmcmp.c src/pgm.c src/filter.h | bin
	$(CC) $(CFLAGS) -o $@ tools/pgmcmp.c src/pgm.c $(LDLIBS)

bin/test_correct: tests/test_correct.c $(LIBSRC) src/filter.h | bin
	$(CC) $(CFLAGS) $(OMP) -o $@ tests/test_correct.c $(LIBSRC) $(LDLIBS)

bin:
	mkdir -p bin

# Jalankan verifikasi correctness (manual + acak vs referensi naif)
test: bin/test_correct
	mkdir -p results
	./bin/test_correct | tee results/test_output.txt

# Buat citra uji 2000x2000
data: bin/gen_pgm
	mkdir -p data
	./bin/gen_pgm -w 2000 -h 2000 -o data/input_2000.pgm

# Benchmark penuh -> results/results.csv (variabel: SIZES, REPEATS, THREADS)
bench: all data
	bash scripts/bench.sh

# Hitung LOC & buat laporan PDF (isi NIM/NAMA)
report:
	python3 tools/make_report.py --nim "$(NIM)" --nama "$(NAMA)"

loc:
	@wc -l src/filter.c src/par_pthreads.c src/par_openmp.c src/pgm.c src/main.c

clean:
	rm -rf bin out/*.pgm
