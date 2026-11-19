/*
 * abyss-splash-render OUT.png WIDTH HEIGHT LOGO.png
 *
 * Writes a WIDTHxHEIGHT black picture with LOGO.png (alpha allowed) drawn
 * in the middle at its own size, as an 8-bit RGB PNG without interlacing
 * (the PNG flavour GRUB's reader understands). abyss-boot-splash uses it to
 * make GRUB's background match the screen exactly, so the logo is never
 * stretched or blurred.
 */
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
	GError *err = NULL;
	GdkPixbuf *logo, *canvas;
	long w, h;
	int lw, lh;

	if (argc != 5) {
		fprintf(stderr, "usage: %s OUT.png WIDTH HEIGHT LOGO.png\n", argv[0]);
		return 2;
	}
	w = strtol(argv[2], NULL, 10);
	h = strtol(argv[3], NULL, 10);
	if (w < 320 || h < 200 || w > 16384 || h > 16384) {
		fprintf(stderr, "%s: bad size %sx%s\n", argv[0], argv[2], argv[3]);
		return 2;
	}
	logo = gdk_pixbuf_new_from_file(argv[4], &err);
	if (!logo) {
		fprintf(stderr, "%s: %s\n", argv[0], err->message);
		return 1;
	}
	lw = gdk_pixbuf_get_width(logo);
	lh = gdk_pixbuf_get_height(logo);
	if (lw > w || lh > h) {
		fprintf(stderr, "%s: logo larger than the screen\n", argv[0]);
		return 1;
	}
	canvas = gdk_pixbuf_new(GDK_COLORSPACE_RGB, FALSE, 8, (int)w, (int)h);
	if (!canvas) {
		fprintf(stderr, "%s: out of memory\n", argv[0]);
		return 1;
	}
	gdk_pixbuf_fill(canvas, 0x000000ff);
	/* 1:1 copy, alpha-blended over black */
	gdk_pixbuf_composite(logo, canvas, (int)(w - lw) / 2, (int)(h - lh) / 2, lw, lh,
	                     (double)((w - lw) / 2), (double)((h - lh) / 2), 1.0, 1.0,
	                     GDK_INTERP_NEAREST, 255);
	if (!gdk_pixbuf_save(canvas, argv[1], "png", &err, "compression", "9", NULL)) {
		fprintf(stderr, "%s: %s\n", argv[0], err->message);
		return 1;
	}
	return 0;
}
