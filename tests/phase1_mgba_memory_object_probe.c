/* Bounded host probe using pinned mGBA headers, allocator, and HLE BIOS data. */
#include <mgba/internal/arm/macros.h>
#include <mgba/internal/gba/memory.h>
#include <mgba/internal/gba/video.h>
#include <mgba-util/memory.h>

#include "gba/hle-bios.h"

#include <stdint.h>
#include <stdio.h>

#if !defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error This probe expects the little-endian host macro branch.
#endif

static int aligned_for_u32(const void* pointer) {
	return (uintptr_t) pointer % _Alignof(uint32_t) == 0;
}

int main(void) {
	struct GBAVideo video = { 0 };
	uint32_t* wram = anonymousMemoryMap(GBA_SIZE_EWRAM + GBA_SIZE_IWRAM);
	uint32_t* iwram;
	uint32_t* rom = anonymousMemoryMap(64);
	video.vram = anonymousMemoryMap(GBA_SIZE_VRAM);
	if (!wram || !rom || !video.vram) {
		return 2;
	}
	iwram = &wram[GBA_SIZE_EWRAM >> 2];

	if (!aligned_for_u32(wram) || !aligned_for_u32(iwram) ||
	    !aligned_for_u32(rom) || !aligned_for_u32(video.vram) ||
	    !aligned_for_u32(video.palette) || !aligned_for_u32(video.oam.raw) ||
	    !aligned_for_u32(hleBios)) {
		fprintf(stderr, "an original-source backing pointer is not uint32_t-aligned\n");
		return 3;
	}

	uint32_t word = 0x44332211;
	uint16_t low;
	uint16_t high;
	uint32_t biosWord;
	STORE_32(word, 0, video.palette);
	LOAD_16(low, 0, video.palette);
	LOAD_16(high, 2, video.palette);
	if (low != 0x2211 || high != 0x4433) {
		return 4;
	}

	STORE_32(word, 0, video.oam.raw);
	if (video.oam.raw[0] != 0x2211 || video.oam.raw[1] != 0x4433) {
		return 5;
	}

	STORE_32(word, 0, video.vram);
	LOAD_16(low, 0, video.vram);
	LOAD_16(high, 2, video.vram);
	if (low != 0x2211 || high != 0x4433) {
		return 6;
	}

	STORE_32(word, 0, wram);
	LOAD_16(low, 0, wram);
	if (low != 0x2211) {
		return 7;
	}
	STORE_32(word, 0, iwram);
	LOAD_16(low, 0, iwram);
	if (low != 0x2211) {
		return 8;
	}

	STORE_32(word, 0, rom);
	LOAD_16(low, 0, rom);
	if (low != 0x2211) {
		return 9;
	}

	LOAD_32(biosWord, 0, hleBios);
	if (biosWord != 0xEA0000D3) {
		return 10;
	}

	printf("ARM_MEMORY_CALLER_ALIGNMENT_PASS "
	       "palette=%zu oam=%zu vram=%zu wram=%zu iwram=%zu rom=%zu hle_bios=%zu\n",
	       (size_t) ((uintptr_t) video.palette % _Alignof(uint32_t)),
	       (size_t) ((uintptr_t) video.oam.raw % _Alignof(uint32_t)),
	       (size_t) ((uintptr_t) video.vram % _Alignof(uint32_t)),
	       (size_t) ((uintptr_t) wram % _Alignof(uint32_t)),
	       (size_t) ((uintptr_t) iwram % _Alignof(uint32_t)),
	       (size_t) ((uintptr_t) rom % _Alignof(uint32_t)),
	       (size_t) ((uintptr_t) hleBios % _Alignof(uint32_t)));

	mappedMemoryFree(wram, GBA_SIZE_EWRAM + GBA_SIZE_IWRAM);
	mappedMemoryFree(rom, 64);
	mappedMemoryFree(video.vram, GBA_SIZE_VRAM);
	return 0;
}
