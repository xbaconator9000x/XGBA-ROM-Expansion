#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <mgba-util/vfs.h>

static int failures;

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	UNUSED(vf);
	UNUSED(buffer);
	UNUSED(size);
	return -1;
}

static void check(const char* label, bool condition) {
	printf("%s %s\n", condition ? "PASS" : "FAIL", label);
	if (!condition) {
		++failures;
	}
}

int main(void) {
	const uint8_t seed[4] = { 0x11, 0x22, 0x33, 0x44 };
	const uint8_t marker = 0xE7;
	struct VFile* vf = VFileMemChunk(seed, sizeof(seed));
	uint8_t* first_mapping;
	uint8_t* expanded_mapping;
	uint8_t* current_mapping;
	uintptr_t first_mapping_address;
	ssize_t written;
	bool closed;

	puts("SCOPE unchanged pinned memory.c and vfs-mem.c; owned VFileMemChunk growth, shrink/regrow within capacity, and close; GBA caller not executed");
	check("constructor owns a copied four-byte buffer", vf
		&& vf->size(vf) == 4
		&& (first_mapping = vf->map(vf, 4, MAP_READ)) != NULL
		&& first_mapping != seed
		&& !memcmp(first_mapping, seed, sizeof(seed)));
	if (!vf) {
		puts("SUMMARY assertions=6 failures=1");
		return 1;
	}

	first_mapping_address = (uintptr_t) first_mapping;
	vf->truncate(vf, 5);
	expanded_mapping = vf->map(vf, 5, MAP_READ);
	check("growth replaces backing, preserves old bytes, and exposes a zero-filled byte",
		vf->size(vf) == 5 && expanded_mapping
		&& (uintptr_t) expanded_mapping != first_mapping_address
		&& !memcmp(expanded_mapping, seed, sizeof(seed))
		&& expanded_mapping[4] == 0
		&& !memcmp(seed, (const uint8_t[]){ 0x11, 0x22, 0x33, 0x44 }, sizeof(seed)));

	current_mapping = NULL;
	check("write places a marker in spare owned capacity",
		vf->seek(vf, 4, SEEK_SET) == 4
		&& (written = vf->write(vf, &marker, sizeof(marker))) == 1
		&& vf->size(vf) == 5
		&& (current_mapping = vf->map(vf, 5, MAP_READ)) != NULL
		&& current_mapping[4] == marker);

	vf->truncate(vf, 3);
	check("shrink clamps the cursor to the new logical end",
		vf->size(vf) == 3 && vf->seek(vf, 0, SEEK_CUR) == 3);

	vf->truncate(vf, 5);
	expanded_mapping = vf->map(vf, 5, MAP_READ);
	check("regrowth within retained capacity makes the truncated marker visible again",
		vf->size(vf) == 5 && expanded_mapping && expanded_mapping[4] == marker
		&& !memcmp(expanded_mapping, seed, sizeof(seed)));

	closed = vf->close(vf);
	check("owned chunk closes successfully and the caller seed remains unchanged",
		closed && !memcmp(seed, (const uint8_t[]){ 0x11, 0x22, 0x33, 0x44 }, sizeof(seed)));

	printf("SUMMARY assertions=%d failures=%d\n", 6, failures);
	return failures ? 1 : 0;
}
