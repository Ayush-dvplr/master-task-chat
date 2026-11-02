"""Decoder for disk_pages.bin."""
import struct

MAGIC = b"CPG1"


def _text(buf, off):
    (n,) = struct.unpack_from(">H", buf, off)
    off += 2
    return buf[off:off + n].decode("ascii"), off + n


def decode(buf):
    """Return a list of frames: dicts with image, page, page_lsn, slots."""
    if buf[:4] != MAGIC:
        raise ValueError("disk_pages.bin does not start with CPG1")
    frames = []
    off = 4
    while off < len(buf):
        image, off = _text(buf, off)
        page, off = _text(buf, off)
        (page_lsn,) = struct.unpack_from(">Q", buf, off)
        page_lsn &= 0xFFFFFFFF
        (count,) = struct.unpack_from(">H", buf, off + 8)
        off += 10
        slots = list(struct.unpack_from(">%dQ" % count, buf, off))
        off += 8 * count
        off += 4
        frames.append({"image": image, "page": page, "page_lsn": page_lsn, "slots": slots})
    return frames
