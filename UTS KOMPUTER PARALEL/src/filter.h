/*
 * filter.h - Antarmuka umum untuk filter konvolusi citra grayscale.
 *
 * Tiga implementasi berbagi inti perhitungan yang sama (filter_row):
 *   - convolve_serial    : baseline satu thread           (filter.c)
 *   - convolve_pthreads  : POSIX Threads, manual          (par_pthreads.c)
 *   - convolve_openmp    : OpenMP, compiler directive     (par_openmp.c)
 * Dengan begitu perbedaan performa murni berasal dari mekanisme paralelisasi.
 */
#ifndef FILTER_H
#define FILTER_H

#include <stddef.h>

typedef struct {
    int w, h;                 /* lebar, tinggi (piksel)            */
    unsigned char *data;      /* row-major, ukuran w*h byte        */
} Image;

typedef enum { FILTER_GAUSSIAN = 0, FILTER_SOBEL = 1 } FilterType;
typedef enum { BORDER_ZERO = 0, BORDER_REPLICATE = 1 } BorderMode;

/* Radius kernel: Gaussian 5x5 -> 2, Sobel 3x3 -> 1 */
int filter_radius(FilterType f);

/* Hitung SATU baris output y (0 <= y < h). Thread-safe: hanya membaca `in`
 * dan hanya menulis baris y dari `out`. Ini satuan kerja terkecil yang
 * dibagikan ke thread. */
void filter_row(const Image *in, Image *out, FilterType f, BorderMode b, int y);

/* Versi serial (baseline). */
void convolve_serial(const Image *in, Image *out, FilterType f, BorderMode b);

/* Versi paralel. Return 0 jika sukses, non-zero jika gagal. */
int  convolve_pthreads(const Image *in, Image *out, FilterType f, BorderMode b, int nthreads);
void convolve_openmp  (const Image *in, Image *out, FilterType f, BorderMode b, int nthreads);

/* ---- I/O PGM (P5 biner atau P2 ASCII, maxval <= 255), tanpa library ---- */
int  pgm_read (const char *path, Image *img);   /* 0 = ok */
int  pgm_write(const char *path, const Image *img);
int  image_alloc(Image *img, int w, int h);
void image_free(Image *img);

#endif
