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
    /* XGetImage requires the requested part of the window to be on screen. */
    Window win = strtoul(argv[1], NULL, 0), child, root = DefaultRootWindow(d);
    XWindowAttributes screen;
    int x, y;
    if (!XGetWindowAttributes(d, root, &screen) ||
        !XTranslateCoordinates(d, win, root, 0, 0, &x, &y, &child)) return 1;
    int left = x < 0 ? -x : 0, top = y < 0 ? -y : 0;
    int width = a.width - left, height = a.height - top;
    int available_width = screen.width - (x > 0 ? x : 0);
    int available_height = screen.height - (y > 0 ? y : 0);
    if (width > available_width) width = available_width;
    if (height > available_height) height = available_height;
    if (width <= 0 || height <= 0) return 1;
    XImage *im = XGetImage(d, win, left, top, width, height, AllPlanes, ZPixmap);
    a.width = width; a.height = height;
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
