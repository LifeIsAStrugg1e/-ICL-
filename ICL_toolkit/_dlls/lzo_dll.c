#include "minilzo.h"
#include <stdlib.h>

__declspec(dllexport) unsigned int lzo_decompress(const unsigned char *in, unsigned int in_len,
                                                   unsigned int out_len, unsigned char *out)
{
    lzo_uint new_len = out_len;
    if (lzo_init() != LZO_E_OK)
        return 0;
    if (lzo1x_decompress_safe(in, in_len, out, &new_len, NULL) != LZO_E_OK)
        return 0;
    return (unsigned int)new_len;
}

__declspec(dllexport) unsigned int lzo_compress(const unsigned char *in, unsigned int in_len,
                                                 unsigned char *out)
{
    static lzo_align_t wrkmem[((LZO1X_1_MEM_COMPRESS) + (sizeof(lzo_align_t) - 1)) / sizeof(lzo_align_t)];
    lzo_uint out_len = 0;
    if (lzo_init() != LZO_E_OK)
        return 0;
    if (lzo1x_1_compress(in, in_len, out, &out_len, wrkmem) != LZO_E_OK)
        return 0;
    return (unsigned int)out_len;
}
