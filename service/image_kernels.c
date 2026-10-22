#ifndef NATIVE_THREADS
#define NATIVE_THREADS 1
#endif
#include <stddef.h>
#include <stdint.h>

/* Build with -ffp-contract=off and no fast-math: preserve each float32 step. */
void sharpen_exact(const float *source, const float *blur, uint8_t *output, size_t n) {
#ifdef _OPENMP
    #pragma omp parallel for schedule(static) num_threads(NATIVE_THREADS) if(n >= 262144)
#endif
    for (size_t i = 0; i < n; ++i) {
        float detail = source[i] - blur[i];
        float value = source[i] * 0.98f;
        value = value + 4.0f;
        detail = detail * 0.22f;
        value = value + detail;
        if (value < 0.0f) value = 0.0f;
        if (value > 255.0f) value = 255.0f;
        output[i] = (uint8_t)value;
    }
}

/* uint8 quarter weights are exact: float32 truncation equals integer / 4. */
void quarter_blend_exact(uint8_t *target, const uint8_t *source, size_t n) {
#ifdef _OPENMP
    #pragma omp parallel for schedule(static) num_threads(NATIVE_THREADS) if(n >= 262144)
#endif
    for (size_t i = 0; i < n; ++i)
        target[i] = (uint8_t)(((uint16_t)target[i] + 3u * source[i]) >> 2);
}
