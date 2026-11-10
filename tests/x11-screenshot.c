/* Save an X11 window as a portable pixmap for inspecting real UI tests. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned char part(unsigned long p, unsigned long mask) {
    if (!mask) return 0;
    while (!(mask & 1)) { p >>= 1; mask >>= 1; }
    return (unsigned char)((p & mask) * 255 / mask);
}
int main(int argc, char **argv) {
    if (argc != 3) return 1;
    Display *d = XOpenDisplay(NULL);
    XWindowAttributes a;
    if (!d || !XGetWindowAttributes(d, strtoul(argv[1], NULL, 0), &a)) return 1;
    /* XGetImage on a partially off-screen window fails with BadMatch. Capture
     * the full root window after confirming the requested window exists. */
    Window root = DefaultRootWindow(d);
    if (!XGetWindowAttributes(d, root, &a)) return 1;
    XImage *im = XGetImage(d, root, 0, 0, a.width, a.height, AllPlanes, ZPixmap);
    if (!im) return 1;
    FILE *out = fopen(argv[2], "wb");
    if (!out) return 1;
    fprintf(out, "P6\n%d %d\n255\n", a.width, a.height);
    for (int y = 0; y < a.height; y++) for (int x = 0; x < a.width; x++) {
        unsigned long p = XGetPixel(im, x, y);
        unsigned char rgb[] = {part(p, im->red_mask), part(p, im->green_mask), part(p, im->blue_mask)};
        fwrite(rgb, 1, 3, out);
    }
    fclose(out); XDestroyImage(im); XCloseDisplay(d); return 0;
}
