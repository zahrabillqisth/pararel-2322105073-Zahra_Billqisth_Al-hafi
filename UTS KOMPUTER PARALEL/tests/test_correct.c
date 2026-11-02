/*
 * test_correct.c - Verifikasi correctness.
 *
 *  1. Tes manual (nilai bisa dihitung dengan tangan) pada citra konstan kecil.
 *  2. Tes acak: bandingkan serial/pthreads/openmp terhadap implementasi
 *     referensi NAIF (independen, tanpa jalur cepat) untuk berbagai ukuran
 *     (termasuk lebih kecil dari kernel & tidak habis dibagi jumlah thread),
 *     kedua filter, kedua mode border, dan jumlah thread 1..16.
 */
#include "../src/filter.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures = 0, checks = 0;
#define CHECK(cond, ...) do { checks++; if (!(cond)) { failures++; printf("  GAGAL: "); printf(__VA_ARGS__); printf("\n"); } } while (0)

/* ---- referensi naif: definisi konvolusi apa adanya ---- */
static int ref_px(const Image *im, int x, int y, BorderMode b)
{
    if (x < 0 || y < 0 || x >= im->w || y >= im->h) {
        if (b == BORDER_ZERO) return 0;
        x = x < 0 ? 0 : (x >= im->w ? im->w - 1 : x);
        y = y < 0 ? 0 : (y >= im->h ? im->h - 1 : y);
    }
    return im->data[y * im->w + x];
}
static void ref_conv(const Image *in, Image *out, FilterType f, BorderMode b)
{
    static const int a[5] = {1, 4, 6, 4, 1};
    static const int gx[3][3] = {{-1,0,1},{-2,0,2},{-1,0,1}};
    static const int gy[3][3] = {{-1,-2,-1},{0,0,0},{1,2,1}};
    for (int y = 0; y < in->h; y++)
        for (int x = 0; x < in->w; x++) {
            if (f == FILTER_GAUSSIAN) {
                int s = 0;
                for (int j = 0; j < 5; j++) for (int i = 0; i < 5; i++)
                    s += a[j] * a[i] * ref_px(in, x + i - 2, y + j - 2, b);
                out->data[y * in->w + x] = (unsigned char)((s + 128) / 256);
            } else {
                int sx = 0, sy = 0;
                for (int j = 0; j < 3; j++) for (int i = 0; i < 3; i++) {
                    int p = ref_px(in, x + i - 1, y + j - 1, b);
                    sx += gx[j][i] * p; sy += gy[j][i] * p;
                }
                double m = sqrt((double)(sx * sx + sy * sy));
                int v = (int)(m + 0.5);
                out->data[y * in->w + x] = (unsigned char)(v > 255 ? 255 : v);
            }
        }
}

static void test_manual(void)
{
    printf("[1] Tes manual (citra konstan 5x5 bernilai 100)\n");
    Image in, out; image_alloc(&in, 5, 5); image_alloc(&out, 5, 5);
    for (int i = 0; i < 25; i++) in.data[i] = 100;

    convolve_serial(&in, &out, FILTER_GAUSSIAN, BORDER_REPLICATE);
    int all100 = 1; for (int i = 0; i < 25; i++) all100 &= (out.data[i] == 100);
    CHECK(all100, "Gaussian+replicate pada citra konstan harus tetap 100");

    convolve_serial(&in, &out, FILTER_GAUSSIAN, BORDER_ZERO);
    /* pusat (2,2): 25 tetangga valid -> 100.
     * sudut (0,0): hanya indeks kernel 2..4 yang valid; bobot 1D = 6+4+1 = 11;
     * jumlah = 11*11*100 = 12100; (12100+128)>>8 = 47 */
    CHECK(out.data[2 * 5 + 2] == 100, "pusat zero-padding = %d (harapan 100)", out.data[12]);
    CHECK(out.data[0] == 47, "sudut (0,0) zero-padding = %d (harapan 47)", out.data[0]);

    convolve_serial(&in, &out, FILTER_SOBEL, BORDER_REPLICATE);
    int all0 = 1; for (int i = 0; i < 25; i++) all0 &= (out.data[i] == 0);
    CHECK(all0, "Sobel+replicate pada citra konstan harus 0 (tidak ada tepi)");

    convolve_serial(&in, &out, FILTER_SOBEL, BORDER_ZERO);
    /* sudut (0,0): gx = 100*(2+1) = 300, gy = 300 -> sqrt(180000)=424 -> clamp 255 */
    CHECK(out.data[0] == 255, "Sobel zero-padding sudut = %d (harapan 255)", out.data[0]);
    CHECK(out.data[12] == 0, "Sobel pusat = %d (harapan 0)", out.data[12]);
    image_free(&in); image_free(&out);
    printf("    selesai\n");
}

static void test_random(void)
{
    printf("[2] Tes acak vs referensi naif (serial, pthreads, openmp)\n");
    static const int sizes[][2] = {{37, 53}, {64, 3}, {5, 5}, {1, 7}, {2, 2}, {100, 41}};
    static const int thr[] = {1, 2, 3, 4, 7, 8, 16};
    srand(42);
    for (unsigned s = 0; s < sizeof sizes / sizeof sizes[0]; s++) {
        int w = sizes[s][0], h = sizes[s][1];
        Image in, ref, got; image_alloc(&in, w, h); image_alloc(&ref, w, h); image_alloc(&got, w, h);
        for (int i = 0; i < w * h; i++) in.data[i] = (unsigned char)(rand() & 255);
        for (int f = 0; f < 2; f++) for (int b = 0; b < 2; b++) {
            ref_conv(&in, &ref, (FilterType)f, (BorderMode)b);
            convolve_serial(&in, &got, (FilterType)f, (BorderMode)b);
            CHECK(!memcmp(ref.data, got.data, (size_t)w * h), "serial %dx%d f=%d b=%d", w, h, f, b);
            for (unsigned t = 0; t < sizeof thr / sizeof thr[0]; t++) {
                memset(got.data, 0xAA, (size_t)w * h);
                CHECK(convolve_pthreads(&in, &got, (FilterType)f, (BorderMode)b, thr[t]) == 0, "pthread_create");
                CHECK(!memcmp(ref.data, got.data, (size_t)w * h), "pthreads %dx%d f=%d b=%d t=%d", w, h, f, b, thr[t]);
                memset(got.data, 0xAA, (size_t)w * h);
                convolve_openmp(&in, &got, (FilterType)f, (BorderMode)b, thr[t]);
                CHECK(!memcmp(ref.data, got.data, (size_t)w * h), "openmp %dx%d f=%d b=%d t=%d", w, h, f, b, thr[t]);
            }
        }
        image_free(&in); image_free(&ref); image_free(&got);
    }
    printf("    selesai\n");
}

int main(void)
{
    test_manual();
    test_random();
    printf("\nHASIL: %d pemeriksaan, %d gagal -> %s\n", checks, failures, failures ? "GAGAL" : "SEMUA LULUS");
    return failures ? 1 : 0;
}
