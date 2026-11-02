/*
 * pgm.c - Baca/tulis PGM (Portable GrayMap) tanpa library eksternal.
 * Mendukung P5 (biner) dan P2 (ASCII) dengan maxval <= 255; komentar # pada
 * header diabaikan. Output selalu P5.
 */
#include "filter.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int image_alloc(Image *img, int w, int h)
{
    img->w = w; img->h = h;
    img->data = (unsigned char *)malloc((size_t)w * h);
    return img->data ? 0 : -1;
}

void image_free(Image *img) { free(img->data); img->data = NULL; }

/* Baca satu integer dari header, lewati spasi & komentar. -1 jika gagal.
 * Tepat satu karakter whitespace setelah angka dikonsumsi; untuk maxval pada
 * P5 inilah perilaku yang diminta spesifikasi PGM. */
static int read_int(FILE *fp)
{
    int c;
    do {
        c = fgetc(fp);
        if (c == 0x23) { while (c != 0x0A && c != EOF) c = fgetc(fp); }
    } while (c != EOF && isspace(c));
    if (!isdigit(c)) return -1;
    int v = 0;
    while (isdigit(c)) { v = v * 10 + (c - 0x30); c = fgetc(fp); }
    return v;
}

int pgm_read(const char *path, Image *img)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) { perror(path); return -1; }
    char magic[3] = {0};
    if (fread(magic, 1, 2, fp) != 2 || magic[0] != 0x50 || (magic[1] != 0x35 && magic[1] != 0x32)) {
        fprintf(stderr, "%s: bukan PGM P5/P2\n", path); fclose(fp); return -1;
    }
    int w = read_int(fp), h = read_int(fp), maxv = read_int(fp);
    if (w <= 0 || h <= 0 || maxv <= 0 || maxv > 255) {
        fprintf(stderr, "%s: header PGM tidak valid\n", path); fclose(fp); return -1;
    }
    if (image_alloc(img, w, h)) { fclose(fp); return -1; }
    size_t n = (size_t)w * h;
    if (magic[1] == 0x35) {
        if (fread(img->data, 1, n, fp) != n) {
            fprintf(stderr, "%s: data piksel kurang\n", path);
            image_free(img); fclose(fp); return -1;
        }
    } else {
        for (size_t i = 0; i < n; i++) {
            int v = read_int(fp);
            if (v < 0) { fprintf(stderr, "%s: data ASCII rusak\n", path);
                         image_free(img); fclose(fp); return -1; }
            img->data[i] = (unsigned char)v;
        }
    }
    fclose(fp);
    return 0;
}

int pgm_write(const char *path, const Image *img)
{
    FILE *fp = fopen(path, "wb");
    if (!fp) { perror(path); return -1; }
    fprintf(fp, "P5\n%d %d\n255\n", img->w, img->h);
    size_t n = (size_t)img->w * img->h;
    int ok = (fwrite(img->data, 1, n, fp) == n);
    if (fclose(fp) != 0) ok = 0;
    return ok ? 0 : -1;
}
