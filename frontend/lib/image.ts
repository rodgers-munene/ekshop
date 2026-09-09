// Client-side downscaling for uploaded images.
//
// Product photos come off phones at 12MP and several MB, but the largest they
// ever render is the 480px-tall detail gallery, and product images are served
// as plain <img> (no next/image), so the browser downloads whatever we stored.
// Capping the long edge at 2048px covers every surface even at 3x DPI while
// cutting a typical 4MB photo to well under a megabyte.
//
// Everything here is best-effort: if the file can't be decoded or re-encoded,
// the original is returned untouched and the server has the final say on
// whether it's acceptable.

// Big enough for the largest surface any upload reaches (the 480px-tall product
// gallery) even at 3x DPI. Callers uploading something only ever shown small --
// a category icon -- should pass a tighter cap.
const MAX_EDGE = 2048;
const QUALITY = 0.9;

// Under this, re-encoding costs more in generation loss than it saves in bytes.
const SKIP_UNDER_BYTES = 300 * 1024;

// Category icons render at 40px in admin and in a small homepage grid, so they
// never need more than this even on a dense display.
export const ICON_MAX_EDGE = 512;

// Must stay in sync with ALLOWED_CONTENT_TYPES in backend/app/services/storage.py.
const ENCODABLE: Record<string, string> = {
  "image/webp": "webp",
  "image/jpeg": "jpg",
  "image/png": "png",
};

// Formats we deliberately pass through rather than rasterise: GIF would be
// flattened to its first frame, and SVG would turn a rejected vector upload
// into an accepted raster one. Both are rejected by the API anyway.
const PASS_THROUGH = new Set(["image/gif", "image/svg+xml"]);

export async function prepareImageForUpload(file: File, maxEdge = MAX_EDGE): Promise<File> {
  if (!file.type.startsWith("image/") || PASS_THROUGH.has(file.type)) return file;
  if (typeof createImageBitmap !== "function") return file;

  let bitmap: ImageBitmap | null = null;
  try {
    // `from-image` applies the EXIF orientation, so portrait phone photos don't
    // come out sideways once the tag is dropped by the re-encode.
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });

    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size <= SKIP_UNDER_BYTES) return file;

    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/webp", QUALITY),
    );
    // A browser that can't encode WebP silently falls back to PNG, so trust the
    // blob's own type rather than what we asked for.
    const extension = blob && ENCODABLE[blob.type];
    if (!blob || !extension) return file;

    // Already-optimised files can come out bigger than they went in.
    if (blob.size >= file.size) return file;

    const base = file.name.replace(/\.[^.]+$/, "") || "image";
    return new File([blob], `${base}.${extension}`, {
      type: blob.type,
      lastModified: file.lastModified,
    });
  } catch {
    // Undecodable (HEIC, corrupt, out of memory) -- upload it as-is.
    return file;
  } finally {
    bitmap?.close();
  }
}
