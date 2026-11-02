/*
 * gen_pgm.c - Pembangkit citra uji PGM sintetis (deterministik, seed tetap).
 * Isi: gradien + lingkaran + persegi + noise LCG, sehingga ada tepi tajam
 * (untuk Sobel) dan derau (untuk Gaussian).
 * Pemakaian: gen_pgm -w 2000 -h 2000 -o data/input_2000.pgm
 */
#include "../src/filter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned int lcg_state = 42;                  /* seed tetap = reproducible */
static unsigned int lcg(void) { lcg_state = lcg_state * 1664525u + 1013904223u; return lcg_state >> 8; }

int main(int argc, char **argv)
{
    int w = 2000, h = 2000; const char *out = "data/input.pgm";
    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "-w") && i + 1 < argc) w = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-h") && i + 1 < argc) h = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else { fprintf(stderr, "Pemakaian: %s -w W -h H -o file.pgm\n", argv[0]); return 2; }
    }
    Image img;
    if (image_alloc(&img, w, h)) return 1;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            int v = (x * 128) / w + (y * 64) / h;            /* gradien */
            int cx = x - w / 2, cy = y - h / 2;
            long long r2 = (long long)cx * cx + (long long)cy * cy, R = (long long)(h / 4) * (h / 4);
            if (r2 < R) v += 60;                              /* lingkaran */
            if (x > w / 8 && x < w / 3 && y > h / 8 && y < h / 3) v -= 50;  /* persegi */
            v += (int)(lcg() % 31) - 15;                      /* noise */
            img.data[(size_t)y * w + x] = (unsigned char)(v < 0 ? 0 : v > 255 ? 255 : v);
        }
    int rc = pgm_write(out, &img);
    image_free(&img);
    return rc ? 1 : 0;
}
