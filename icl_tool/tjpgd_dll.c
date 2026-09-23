#include "tjpgd.h"
#include <stdlib.h>
#include <string.h>

static unsigned char *g_src;
static unsigned int g_src_len;
static unsigned int g_src_pos;
static unsigned char *g_dst;

static unsigned short in_func(JDEC *jd, unsigned char *buf, unsigned short num)
{
    unsigned int avail = g_src_len - g_src_pos;
    unsigned int n = (num < avail) ? num : avail;
    if (buf)
        memcpy(buf, g_src + g_src_pos, n);
    g_src_pos += n;
    return (unsigned short)n;
}

static unsigned short out_func(JDEC *jd, void *bitmap, JRECT *rect)
{
    unsigned char *src = (unsigned char *)bitmap;
    unsigned char *dst = g_dst + 2 * (rect->top * jd->width + rect->left);
    unsigned int bws = 2 * (rect->right - rect->left + 1);
    unsigned int bwd = 2 * jd->width;
    unsigned int y;
    for (y = rect->top; y <= rect->bottom; y++)
    {
        memcpy(dst, src, bws);
        src += bws;
        dst += bwd;
    }
    return 1;
}

/* Decode JPEG -> RGB565. Returns malloc'd buffer (free with tjpgd_free), or NULL. */
__declspec(dllexport) unsigned short *tjpgd_decode(const unsigned char *jpg, unsigned int len,
                                                    unsigned int *width, unsigned int *height)
{
    static unsigned char pool[4096];
    JDEC jd;

    g_src = (unsigned char *)jpg;
    g_src_len = len;
    g_src_pos = 0;
    g_dst = NULL;

    if (jd_prepare(&jd, in_func, pool, sizeof(pool), NULL) != JDR_OK)
        return NULL;

    g_dst = (unsigned char *)malloc((unsigned int)jd.width * jd.height * 2);
    if (!g_dst)
        return NULL;

    if (jd_decomp(&jd, out_func, 0) != JDR_OK)
    {
        free(g_dst);
        g_dst = NULL;
        return NULL;
    }

    if (width)  *width  = jd.width;
    if (height) *height = jd.height;
    return (unsigned short *)g_dst;
}

__declspec(dllexport) void tjpgd_free(void *p)
{
    free(p);
}
