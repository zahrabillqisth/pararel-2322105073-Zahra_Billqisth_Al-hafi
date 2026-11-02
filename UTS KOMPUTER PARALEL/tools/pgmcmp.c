/*
 * pgmcmp.c - Bandingkan dua PGM byte-per-byte. Exit 0 jika identik, 1 jika beda.
 */
#include "../src/filter.h"
#include <stdio.h>

int main(int argc, char **argv)
{
    if (argc != 3) { fprintf(stderr, "Pemakaian: %s a.pgm b.pgm\n", argv[0]); return 2; }
    Image a, b;
    if (pgm_read(argv[1], &a)) return 2;
    if (pgm_read(argv[2], &b)) return 2;
    if (a.w != b.w || a.h != b.h) { printf("BEDA: ukuran %dx%d vs %dx%d\n", a.w, a.h, b.w, b.h); return 1; }
    size_t n = (size_t)a.w * a.h, diff = 0, first = 0;
    for (size_t i = 0; i < n; i++)
        if (a.data[i] != b.data[i]) { if (!diff) first = i; diff++; }
    if (diff) { printf("BEDA: %zu piksel berbeda (pertama di x=%zu y=%zu)\n", diff, first % a.w, first / a.w); return 1; }
    printf("IDENTIK (%dx%d, %zu piksel)\n", a.w, a.h, n);
    return 0;
}
