/*
 * par_pthreads.c - Paralelisasi EKSPLISIT dengan POSIX Threads.
 *
 * Strategi workload : dekomposisi domain per BLOK BARIS kontigu (static).
 *   Citra h baris dibagi ke p thread; thread i mendapat h/p baris (+1 bila
 *   i < h%p) sehingga selisih beban maksimal 1 baris.
 * Border / halo     : setiap thread MEMBACA baris di luar bandnya (halo
 *   selebar radius baris) langsung dari citra input yang read-only, jadi
 *   tidak perlu menyalin region overlap dan tidak perlu komunikasi.
 * Sinkronisasi      : output tiap thread berada di baris yang saling lepas
 *   (tidak ada write-write conflict) dan input hanya dibaca, sehingga TIDAK
 *   butuh mutex. Satu-satunya sinkronisasi adalah pthread_join (barrier
 *   implisit di akhir). Thread utama ikut mengerjakan band 0.
 */
#include "filter.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    const Image *in;
    Image       *out;
    FilterType   f;
    BorderMode   b;
    int          y0, y1;          /* band baris [y0, y1) */
} Task;

static void *worker(void *arg)
{
    const Task *t = (const Task *)arg;
    for (int y = t->y0; y < t->y1; y++)
        filter_row(t->in, t->out, t->f, t->b, y);
    return NULL;
}

int convolve_pthreads(const Image *in, Image *out, FilterType f, BorderMode b, int nthreads)
{
    if (nthreads < 1) nthreads = 1;
    if (nthreads > in->h) nthreads = in->h;           /* jangan lebih dari jumlah baris */

    pthread_t *th = (pthread_t *)malloc(sizeof(pthread_t) * nthreads);
    Task      *tk = (Task *)calloc((size_t)nthreads, sizeof(Task));
    if (!th || !tk) { free(th); free(tk); return -1; }

    const int base = in->h / nthreads, rem = in->h % nthreads;
    int y = 0;
    for (int i = 0; i < nthreads; i++) {              /* partisi workload */
        int rows = base + (i < rem ? 1 : 0);
        tk[i] = (Task){ in, out, f, b, y, y + rows };
        y += rows;
    }

    int created = 0, err = 0;
    for (int i = 1; i < nthreads; i++) {              /* thread 1..p-1 */
        if (pthread_create(&th[i], NULL, worker, &tk[i]) != 0) { err = -1; break; }
        created++;
    }
    if (!err) worker(&tk[0]);                         /* thread utama = band 0 */
    else      fprintf(stderr, "pthread_create gagal\n");

    for (int i = 1; i <= created; i++)                /* barrier: tunggu semua */
        pthread_join(th[i], NULL);

    if (err) convolve_serial(in, out, f, b);          /* fallback agar hasil tetap benar */
    free(th); free(tk);
    return err;
}
