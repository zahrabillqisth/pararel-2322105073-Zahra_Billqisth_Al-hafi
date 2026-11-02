/*
 * main.c - Driver: baca PGM -> konvolusi (serial / pthreads / openmp) -> tulis PGM.
 * Mengukur waktu baca, komputasi (median dari beberapa repetisi), dan tulis
 * secara terpisah untuk analisis I/O-bound vs compute-bound.
 *
 * Pemakaian:
 *   conv -i in.pgm -o out.pgm [-m serial|pthreads|openmp] [-t N]
 *        [-f gaussian|sobel] [-b zero|replicate] [-r REPEAT] [--csv]
 */
#include "filter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static int cmp_double(const void *a, const void *b)
{
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static void usage(const char *p)
{
    fprintf(stderr,
        "Pemakaian: %s -i in.pgm -o out.pgm [-m serial|pthreads|openmp] [-t N]\n"
        "           [-f gaussian|sobel] [-b zero|replicate] [-r REPEAT] [--csv]\n", p);
}

int main(int argc, char **argv)
{
    const char *in_path = NULL, *out_path = NULL, *mode = "serial";
    FilterType f = FILTER_GAUSSIAN; BorderMode b = BORDER_REPLICATE;
    int threads = 1, repeat = 5, csv = 0;

    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "-i") && i + 1 < argc) in_path  = argv[++i];
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out_path = argv[++i];
        else if (!strcmp(argv[i], "-m") && i + 1 < argc) mode     = argv[++i];
        else if (!strcmp(argv[i], "-t") && i + 1 < argc) threads  = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-r") && i + 1 < argc) repeat   = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-f") && i + 1 < argc) {
            const char *s = argv[++i];
            if      (!strcmp(s, "gaussian")) f = FILTER_GAUSSIAN;
            else if (!strcmp(s, "sobel"))    f = FILTER_SOBEL;
            else { usage(argv[0]); return 2; }
        } else if (!strcmp(argv[i], "-b") && i + 1 < argc) {
            const char *s = argv[++i];
            if      (!strcmp(s, "zero"))      b = BORDER_ZERO;
            else if (!strcmp(s, "replicate")) b = BORDER_REPLICATE;
            else { usage(argv[0]); return 2; }
        } else if (!strcmp(argv[i], "--csv")) csv = 1;
        else { usage(argv[0]); return 2; }
    }
    if (!in_path || !out_path || threads < 1 || repeat < 1) { usage(argv[0]); return 2; }
    int m_serial = !strcmp(mode, "serial"), m_pth = !strcmp(mode, "pthreads"),
        m_omp = !strcmp(mode, "openmp");
    if (!m_serial && !m_pth && !m_omp) { usage(argv[0]); return 2; }
    if (m_serial) threads = 1;

    Image in, out;
    double t0 = now_ms();
    if (pgm_read(in_path, &in)) return 1;
    double read_ms = now_ms() - t0;
    if (image_alloc(&out, in.w, in.h)) { fprintf(stderr, "malloc gagal\n"); return 1; }

    #define RUN() do { \
        if (m_serial)    convolve_serial(&in, &out, f, b); \
        else if (m_pth)  { if (convolve_pthreads(&in, &out, f, b, threads)) return 1; } \
        else             convolve_openmp(&in, &out, f, b, threads); \
    } while (0)

    RUN();                                            /* warm-up (page fault, cache) */
    double *ts = (double *)malloc(sizeof(double) * repeat);
    for (int r = 0; r < repeat; r++) {
        double s = now_ms();
        RUN();
        ts[r] = now_ms() - s;
    }
    qsort(ts, repeat, sizeof(double), cmp_double);
    double compute_ms = ts[repeat / 2], compute_min = ts[0];

    t0 = now_ms();
    if (pgm_write(out_path, &out)) return 1;
    double write_ms = now_ms() - t0;

    if (csv)
        printf("%d,%s,%s,%s,%d,%.3f,%.3f,%.3f,%.3f\n", in.w,
               f == FILTER_GAUSSIAN ? "gaussian" : "sobel",
               b == BORDER_ZERO ? "zero" : "replicate",
               mode, threads, read_ms, compute_ms, compute_min, write_ms);
    else
        printf("mode=%s threads=%d filter=%s border=%s size=%dx%d\n"
               "  read=%.3f ms  compute(median of %d)=%.3f ms (min %.3f)  write=%.3f ms\n",
               mode, threads, f == FILTER_GAUSSIAN ? "gaussian" : "sobel",
               b == BORDER_ZERO ? "zero" : "replicate", in.w, in.h,
               read_ms, repeat, compute_ms, compute_min, write_ms);

    free(ts); image_free(&in); image_free(&out);
    return 0;
}
