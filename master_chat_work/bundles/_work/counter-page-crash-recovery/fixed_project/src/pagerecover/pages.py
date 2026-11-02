"""Decoder for disk_pages.bin."""
import struct
import zlib

MAGIC = b"CPG1"


def _text(buf, off):
    (n,) = struct.unpack_from(">H", buf, off)
    off += 2
    return buf[off:off + n].decode("ascii"), off + n


def decode(buf):
    """Return a list of frames: dicts with image, page, page_lsn, slots and crc_ok."""
    if buf[:4] != MAGIC:
        raise ValueError("disk_pages.bin does not start with CPG1")
    frames = []
    off = 4
    while off < len(buf):
        start = off
        image, off = _text(buf, off)
        page, off = _text(buf, off)
        page_lsn, count = struct.unpack_from(">QH", buf, off)
        off += 10
        slots = list(struct.unpack_from(">%dq" % count, buf, off))
        off += 8 * count
        (crc,) = struct.unpack_from(">I", buf, off)
        crc_ok = zlib.crc32(buf[start:off]) == crc
        off += 4
        frames.append({"image": image, "page": page, "page_lsn": page_lsn, "slots": slots,
                       "crc_ok": crc_ok})
    return frames
