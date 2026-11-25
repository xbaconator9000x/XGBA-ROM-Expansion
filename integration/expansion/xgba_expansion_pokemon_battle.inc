/*
 * Source-authentic Pokemon battle sprite bridge for the pinned RHH build.
 * Spliced into src/battle_gfx_sfx_util.c immediately before the ORIGINAL
 * BattleLoadMonSpriteGfx. The original HandleLoadSpecialPokePic remains the
 * fallback; the palette load and every animation table stay engine-owned.
 *
 * Only whole front/back tile streams of an explicit species allowlist are
 * replaced, and only inside the engine's own battler sprite buffer.
 */
#include "XGBA_BATTLE_PAGE_API"
#include "constants/species.h"
#include "pokemon_spots.h"

extern void XgbaExpansionMonAttempt(u32 isFront, u32 species);
extern void XgbaExpansionMonTransfer(u32 isFront, u32 species, const void *dest, u32 bytes);
extern void XgbaExpansionMonFallback(u32 isFront, u32 species, const void *dest, u32 bytes);

static u32 XgbaExpansionMonHash(const u8 *data, u32 bytes)
{
    u32 hash = 2166136261u;
    for (u32 i = 0; i < bytes; ++i)
        hash = (hash ^ data[i]) * 16777619u;
    return hash;
}

static bool8 XgbaExpansionMonLeaseIntact(const u8 *page, u32 generation, u32 bytes)
{
    return XgbaExpansionPageGeneration() == generation
        && XgbaExpansionPageData() == page
        && XgbaExpansionPageResidentBytes() == bytes;
}

/* The ROM stream the original loader would decompress, or NULL whenever the
 * original path must run: unlisted species, gender/spot variants that alter
 * the tiles after decompression, GBA-style graphics, or non-image streams. */
static const u32 *XgbaExpansionMonSource(bool32 isFront, u32 rawSpecies, u32 *bytes)
{
#if P_GBA_STYLE_SPECIES_GFX
    (void)isFront; (void)rawSpecies; (void)bytes;
    return NULL;
#else
    enum Species species = SanitizeSpeciesId((enum Species)rawSpecies);
    const u32 *pic;
    u32 size;
    if (species != SPECIES_BULBASAUR && species != SPECIES_GEODUDE)
        return NULL;
#if P_GENDER_DIFFERENCES
    if ((isFront ? gSpeciesInfo[species].frontPicFemale
                 : gSpeciesInfo[species].backPicFemale) != NULL)
        return NULL;
#endif
    if (isFront && ShouldDrawSpotsOnSpecies(species))
        return NULL;
    pic = isFront ? gSpeciesInfo[species].frontPic : gSpeciesInfo[species].backPic;
    if (!pic || (u32)pic < 0x08000000u || (u32)pic > 0x0A000000u - 8u || ((u32)pic & 3u))
        return NULL;
    if (((const union CompressionHeader *)pic)->smol.mode > ENCODE_BOTH_DELTA_SYMS
        || !IsCompressedData(pic))
        return NULL;
    size = GetDecompressedDataSize(pic);
    if (size != MON_PIC_SIZE && !(isFront && size == MON_PIC_SIZE * MAX_MON_PIC_FRAMES))
        return NULL;
    *bytes = size;
    return pic;
#endif
}

/* The pinned allocator owns one contiguous block of MAX_BATTLERS_COUNT
 * slots. A generic EWRAM address is not sufficient: reject interior,
 * stale, aliased or out-of-slot destinations before copying provider data. */
static bool8 XgbaExpansionMonDestinationOwned(const void *dest, u32 bytes)
{
    const u32 slotBytes = MON_PIC_SIZE * MAX_MON_PIC_FRAMES;
    const u32 totalBytes = slotBytes * MAX_BATTLERS_COUNT;
    u32 base;
    if (!gMonSpritesGfxPtr || !gMonSpritesGfxPtr->firstDecompressed
        || !dest || !bytes || bytes > slotBytes)
        return FALSE;
    base = (u32)gMonSpritesGfxPtr->firstDecompressed;
    if ((base & 3u) || base < 0x02000000u
        || base > 0x02040000u - totalBytes)
        return FALSE;
    for (u32 i = 0; i < MAX_BATTLERS_COUNT; ++i)
    {
        const u32 expected = base + i * slotBytes;
        if ((u32)dest == expected
            && (u32)gMonSpritesGfxPtr->spritesGfx[i] == expected)
            return TRUE;
    }
    return FALSE;
}

static bool8 XgbaExpansionTryMonPic(bool32 isFront, void *dest, u32 species)
{
    static const char hex[] = "0123456789abcdef";
    char resource[] = "rhh.mon.f.0000";
    const u32 *original;
    const u8 *page;
    u32 bytes = 0;
    u32 generation;
    u32 sourceHash;
    u32 destinationHash;
    u32 leaseStart;
    u32 destStart = (u32)dest;

    /* Battle sprite loading is a phase boundary: never inherit a stale lease. */
    XgbaExpansionPageRelease();
    original = XgbaExpansionMonSource(isFront, species, &bytes);
    if (!original || !XgbaExpansionMonDestinationOwned(dest, bytes)
        || bytes > XGBA_EXPANSION_PAGE_CAPACITY
        || (destStart & 3u) || destStart < 0x02000000u
        || destStart > 0x02040000u - bytes)
        return FALSE;
    /* The final 16 KiB of gHeap belongs to the lease and must never be a
     * destination. Validate heap geometry before any address arithmetic. */
    if (HEAP_SIZE < XGBA_EXPANSION_PAGE_CAPACITY)
        return FALSE;
    leaseStart = (u32)gHeap + HEAP_SIZE - XGBA_EXPANSION_PAGE_CAPACITY;
    if (leaseStart < 0x02000000u
        || leaseStart > 0x02040000u - XGBA_EXPANSION_PAGE_CAPACITY)
        return FALSE;
    if (destStart < leaseStart + XGBA_EXPANSION_PAGE_CAPACITY && leaseStart < destStart + bytes)
        return FALSE;

    resource[8] = isFront ? 'f' : 'b';
    for (u32 i = 0; i < 4; ++i)
        resource[13u - i] = hex[(species >> (4 * i)) & 15u];
    if (XgbaExpansionPageAcquire(resource, bytes) != bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    page = XgbaExpansionPageData();
    if (!page || ((u32)page & 3u) || (u32)page != leaseStart
        || XgbaExpansionPageResidentBytes() != bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    generation = XgbaExpansionPageGeneration();
    sourceHash = XgbaExpansionMonHash(page, bytes);
    if (!XgbaExpansionMonLeaseIntact(page, generation, bytes))
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    /* Bounded synchronous chunks: a provider generation change between or
     * during chunks aborts to the original decompressor, which rewrites the
     * whole destination. Each chunk is verified before the next is copied. */
    for (u32 offset = 0; offset < bytes; offset += 256u)
    {
        u32 chunk = bytes - offset;
        if (chunk > 256u)
            chunk = 256u;
        if (!XgbaExpansionMonLeaseIntact(page, generation, bytes))
        {
            XgbaExpansionPageRelease();
            return FALSE;
        }
        CpuCopy32(page + offset, (u8 *)dest + offset, chunk);
        if (!XgbaExpansionMonLeaseIntact(page, generation, bytes))
        {
            XgbaExpansionPageRelease();
            return FALSE;
        }
        for (u32 j = 0; j < chunk; ++j)
        {
            if (((const u8 *)dest)[offset + j] != page[offset + j])
            {
                XgbaExpansionPageRelease();
                return FALSE;
            }
        }
    }
    destinationHash = XgbaExpansionMonHash(dest, bytes);
    if (destinationHash != sourceHash
        || XgbaExpansionMonHash(page, bytes) != sourceHash
        || !XgbaExpansionMonLeaseIntact(page, generation, bytes))
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    XgbaExpansionPageRelease();
    /* The release must advance the generation and expose no page, and must
     * leave the engine-owned destination untouched. */
    if (XgbaExpansionPageGeneration() == generation
        || XgbaExpansionPageResidentBytes() != 0u
        || XgbaExpansionPageData() != NULL
        || XgbaExpansionMonHash(dest, bytes) != destinationHash)
        return FALSE;
    {
        u32 releasedGeneration = XgbaExpansionPageGeneration();
        XgbaExpansionMonTransfer(isFront, species, dest, bytes);
        /* The witness is observational; it must not re-lease a page or alter
         * the destination that the battle engine is about to draw. */
        if (XgbaExpansionPageGeneration() != releasedGeneration
            || XgbaExpansionPageResidentBytes() != 0u
            || XgbaExpansionPageData() != NULL)
        {
            XgbaExpansionPageRelease();
            return FALSE;
        }
        if (XgbaExpansionMonHash(dest, bytes) != destinationHash)
            return FALSE;
    }
    return TRUE;
}

/* Observe the tiles produced by the ORIGINAL decompressor, so the disabled
 * build is proven to emit the same authentic bytes as the external source. */
static void XgbaExpansionNoteMonFallback(bool32 isFront, u32 species, const void *dest)
{
    u32 bytes = 0;
    if (dest && XgbaExpansionMonSource(isFront, species, &bytes))
        XgbaExpansionMonFallback(isFront, species, dest, bytes);
}
