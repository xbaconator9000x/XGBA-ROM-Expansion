"""Source-backed R27 original Emerald oversized-map geometry & transfer preflight.

This is a **capacity preflight**, not a proof of rendering. Native pinned
Emerald/mGBA acceptance must separately verify actual source-backed full
map-grid rows, BG VRAM, original controller input and LCD pixels.

MAX_MAP_DATA_SIZE is 0x2800 u16 cells in the pinned pret/pokeemerald.
The original world map adds 15 columns and 14 rows of connection/border.
All arithmetic is Python arbitrary-precision to reject overflow safely.
"""
from dataclasses import dataclass

MAX_MAP_DATA_CELLS = 0x2800
MAP_OFFSET_W = 15
MAP_OFFSET_H = 14
MAX_SINGLE_XGBA_TRANSFER = 16384
EWRAM_PHYSICAL_BYTES = 256 * 1024

class GeometryCapacityError(ValueError):
    pass

@dataclass(frozen=True)
class GeometryPlan:
    width: int
    height: int
    backup_width: int
    backup_height: int
    backup_cells: int
    grid_bytes: int
    packed_bytes: int
    reserved_ewram_bytes: int

def plan_map(width: int, height: int, *, base_pack_without_grid: int,
             transfer_limit: int=MAX_SINGLE_XGBA_TRANSFER) -> GeometryPlan:
    if type(width) is not int or type(height) is not int or not (1 <= width <= 65535 and 1 <= height <= 65535):
        raise GeometryCapacityError("invalid map dimensions: must fit original u16 geometry")
    if type(base_pack_without_grid) is not int or base_pack_without_grid < 32:
        raise GeometryCapacityError("invalid complete tileset/header payload")
    if type(transfer_limit) is not int or not (1 <= transfer_limit <= MAX_SINGLE_XGBA_TRANSFER):
        raise GeometryCapacityError("transfer capacity exceeds the MMIO v1 16KiB contract")
    bw, bh = width + MAP_OFFSET_W, height + MAP_OFFSET_H
    cells = bw * bh
    if cells > MAX_MAP_DATA_CELLS:
        raise GeometryCapacityError(f"original Emerald backup map overflow: {bw}x{bh}={cells} > {MAX_MAP_DATA_CELLS}")
    grid_bytes=width * height * 2
    # For original full secondary tileset, 20x20 map bytes and larger
    # resource chunks are 4-byte aligned. In general packed offsets must
    # be planned with padding, not simply base + grid bytes.
    packed=base_pack_without_grid + grid_bytes + (-grid_bytes % 4)
    if packed > transfer_limit:
        raise GeometryCapacityError(f"single XGBA transfer overflow: {packed} > {transfer_limit}")
    return GeometryPlan(width,height,bw,bh,cells,grid_bytes,packed,packed)

def source_tiled_grid(original: bytes, width: int, height: int) -> bytes:
    """Synthetic stress geometry derived from original 20x20 Emerald tile bytes.

    This produces an author-labelled *test layout*, not a claim that the
    unmodified game shipped a 64x64 Littleroot map. All cells are sourced
    from genuine source-backed original map data; game itself draws them.
    """
    import struct
    if len(original)!=800:
        raise GeometryCapacityError("expected 20x20 original Littleroot source")
    values=struct.unpack("<400H",original)
    return struct.pack("<"+str(width*height)+"H",*(values[(y%20)*20+(x%20)] for y in range(height) for x in range(width)))
