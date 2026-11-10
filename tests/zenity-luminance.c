/* Sample the center of an X11 window, where the file chooser's view is drawn. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned long component(unsigned long pixel, unsigned long mask) {
    if (!mask) return 0;
    while (!(mask & 1)) { pixel >>= 1; mask >>= 1; }
    return (pixel & mask) * 255 / mask;
}
int main(int argc, char **argv) {
    Display *d = XOpenDisplay(NULL);
    XWindowAttributes a;
    if (argc != 2 || !d || !XGetWindowAttributes(d, strtoul(argv[1], NULL, 0), &a)) return 1;
    XImage *im = XGetImage(d, strtoul(argv[1], NULL, 0), 0, 0, a.width, a.height, AllPlanes, ZPixmap);
    if (!im) return 1;
    unsigned long sum = 0, n = 0;
    for (int y = a.height / 3; y < a.height * 4 / 5; y += 4)
        for (int x = a.width / 2; x < a.width * 4 / 5; x += 4) {
            unsigned long p = XGetPixel(im, x, y);
            sum += component(p, im->red_mask) + component(p, im->green_mask) + component(p, im->blue_mask);
            n += 3;
        }
    if (!n) return 1;
    printf("%lu\n", sum / n);
    XDestroyImage(im); XCloseDisplay(d); return 0;
}
