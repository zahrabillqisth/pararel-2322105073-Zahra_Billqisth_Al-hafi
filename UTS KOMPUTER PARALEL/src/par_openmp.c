/*
 * par_openmp.c - Paralelisasi dengan compiler directive OpenMP.
 *
 * Pembagian workload, pembuatan thread, dan barrier di akhir region
 * ditangani runtime OpenMP. Loop terluar (baris) dipilih sebagai target
 * karena iterasinya independen (tiap baris output hanya bergantung pada
 * input yang read-only) dan granularitasnya cukup besar.
 *
 * Scope variabel:
 *   shared  : in, out, f, b, h   (read-only atau ditulis pada indeks terpisah)
 *   private : y                  (variabel loop, otomatis private)
 */
#include "filter.h"

void convolve_openmp(const Image *in, Image *out, FilterType f, BorderMode b, int nthreads)
{
    const int h = in->h;
    #pragma omp parallel for num_threads(nthreads) schedule(static) \
                default(none) shared(in, out, f, b, h)
    for (int y = 0; y < h; y++)
        filter_row(in, out, f, b, y);
}
