/*
 * filter.c - Inti konvolusi (Gaussian 5x5 dan Sobel 3x3) + versi serial.
 *
 * Semua aritmetika memakai integer (kecuali sqrt() pada Sobel yang
 * deterministik menurut IEEE-754), sehingga hasil versi paralel HARUS
 * identik byte-per-byte dengan versi serial.
 *
 * Penanganan border:
 *   BORDER_ZERO      : piksel di luar citra dianggap bernilai 0
 *   BORDER_REPLICATE : koordinat dijepit (clamp) ke piksel tepi terdekat
 * Piksel interior (jarak >= radius dari tepi) memakai jalur cepat tanpa
 * pengecekan batas; hanya piksel tepi yang memakai fetch() dengan pengecekan.
 */
#include "filter.h"
#include <math.h>

/* Gaussian 5x5 = outer product dari [1 4 6 4 1]; jumlah bobot = 256 */
static const int GAUSS5[5][5] = {
    { 1,  4,  6,  4, 1},
    { 4, 16, 24, 16, 4},
    { 6, 24, 36, 24, 6},
    { 4, 16, 24, 16, 4},
    { 1,  4,  6,  4, 1}
};
static const int SOBEL_GX[3][3] = {{-1, 0, 1}, {-2, 0, 2}, {-1, 0, 1}};
static const int SOBEL_GY[3][3] = {{-1,-2,-1}, { 0, 0, 0}, { 1, 2, 1}};

int filter_radius(FilterType f) { return f == FILTER_GAUSSIAN ? 2 : 1; }

/* Ambil piksel (x,y) dengan kebijakan border. Dipakai hanya di area tepi. */
static inline int fetch(const Image *in, int x, int y, BorderMode b)
{
    if (x < 0 || x >= in->w || y < 0 || y >= in->h) {
        if (b == BORDER_ZERO) return 0;
        if (x < 0) x = 0; else if (x >= in->w) x = in->w - 1;
        if (y < 0) y = 0; else if (y >= in->h) y = in->h - 1;
    }
    return in->data[(size_t)y * in->w + x];
}

static inline unsigned char sobel_mag(int gx, int gy)
{
    int v = (int)(sqrt((double)(gx * gx + gy * gy)) + 0.5);
    return (unsigned char)(v > 255 ? 255 : v);
}

/* ---------- jalur tepi (dengan pengecekan batas) ---------- */
static inline unsigned char gauss_edge(const Image *in, int x, int y, BorderMode b)
{
    int s = 0;
    for (int dy = -2; dy <= 2; dy++)
        for (int dx = -2; dx <= 2; dx++)
            s += GAUSS5[dy + 2][dx + 2] * fetch(in, x + dx, y + dy, b);
    return (unsigned char)((s + 128) >> 8);          /* pembulatan /256 */
}

static inline unsigned char sobel_edge(const Image *in, int x, int y, BorderMode b)
{
    int gx = 0, gy = 0;
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++) {
            int p = fetch(in, x + dx, y + dy, b);
            gx += SOBEL_GX[dy + 1][dx + 1] * p;
            gy += SOBEL_GY[dy + 1][dx + 1] * p;
        }
    return sobel_mag(gx, gy);
}

/* ---------- jalur interior (cepat, tanpa pengecekan batas) ---------- */
static inline unsigned char gauss_inner(const unsigned char *c, int w)
{
    int s = 0;
    for (int dy = -2; dy <= 2; dy++) {
        const unsigned char *r = c + (ptrdiff_t)dy * w;
        for (int dx = -2; dx <= 2; dx++)
            s += GAUSS5[dy + 2][dx + 2] * r[dx];
    }
    return (unsigned char)((s + 128) >> 8);
}

static inline unsigned char sobel_inner(const unsigned char *c, int w)
{
    int gx = 0, gy = 0;
    for (int dy = -1; dy <= 1; dy++) {
        const unsigned char *r = c + (ptrdiff_t)dy * w;
        for (int dx = -1; dx <= 1; dx++) {
            gx += SOBEL_GX[dy + 1][dx + 1] * r[dx];
            gy += SOBEL_GY[dy + 1][dx + 1] * r[dx];
        }
    }
    return sobel_mag(gx, gy);
}

void filter_row(const Image *in, Image *out, FilterType f, BorderMode b, int y)
{
    const int w = in->w, h = in->h, r = filter_radius(f);
    unsigned char *o = out->data + (size_t)y * w;
    const int row_inner = (y >= r && y < h - r);
    const int x0 = r, x1 = w - r;                    /* interior: x0 <= x < x1 */

    if (!row_inner || x1 <= x0) {                    /* seluruh baris = tepi   */
        for (int x = 0; x < w; x++)
            o[x] = (f == FILTER_GAUSSIAN) ? gauss_edge(in, x, y, b)
                                          : sobel_edge(in, x, y, b);
        return;
    }
    for (int x = 0; x < x0; x++)                     /* tepi kiri              */
        o[x] = (f == FILTER_GAUSSIAN) ? gauss_edge(in, x, y, b) : sobel_edge(in, x, y, b);

    const unsigned char *src = in->data + (size_t)y * w;
    if (f == FILTER_GAUSSIAN)
        for (int x = x0; x < x1; x++) o[x] = gauss_inner(src + x, w);
    else
        for (int x = x0; x < x1; x++) o[x] = sobel_inner(src + x, w);

    for (int x = x1; x < w; x++)                     /* tepi kanan             */
        o[x] = (f == FILTER_GAUSSIAN) ? gauss_edge(in, x, y, b) : sobel_edge(in, x, y, b);
}

void convolve_serial(const Image *in, Image *out, FilterType f, BorderMode b)
{
    for (int y = 0; y < in->h; y++)
        filter_row(in, out, f, b, y);
}
