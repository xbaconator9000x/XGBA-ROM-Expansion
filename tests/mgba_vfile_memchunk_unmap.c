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
	const uint8_t replacement = 0xA5;
	uint8_t contents[4] = { 0 };
	struct VFile* vf = VFileMemChunk(seed, sizeof(seed));
	void* mapping = NULL;
	void* remapping = NULL;
	ssize_t read;
	ssize_t written;
	bool closed;

	puts("SCOPE unchanged pinned memory.c and vfs-mem.c; owned VFileMemChunk map/unmap round-trip; production rewind caller source-traced only");
	check("constructor maps an owned copy of the four-byte seed",
		vf && (mapping = vf->map(vf, sizeof(seed), MAP_READ)) != NULL
		&& mapping != seed && !memcmp(mapping, seed, sizeof(seed)));
	if (!vf) {
		puts("SUMMARY assertions=6 failures=1");
		return 1;
	}

	check("mapping beyond the logical extent is rejected",
		vf->map(vf, sizeof(seed) + 1, MAP_READ) == NULL);

	vf->unmap(vf, mapping, sizeof(seed));
	check("read after unmap preserves the mapped bytes",
		vf->seek(vf, 0, SEEK_SET) == 0
		&& (read = vf->read(vf, contents, sizeof(contents))) == sizeof(contents)
		&& !memcmp(contents, seed, sizeof(seed)));

	check("writes remain available after unmap",
		vf->seek(vf, 2, SEEK_SET) == 2
		&& (written = vf->write(vf, &replacement, sizeof(replacement))) == 1);
	remapping = vf->map(vf, sizeof(seed), MAP_READ);
	check("a fresh mapping exposes the post-unmap write",
		remapping && ((const uint8_t*) remapping)[2] == replacement
		&& ((const uint8_t*) remapping)[3] == seed[3]);

	vf->unmap(vf, remapping, sizeof(seed));
	closed = vf->close(vf);
	check("close succeeds after unmap and leaves the caller seed unchanged",
		closed && !memcmp(seed, (const uint8_t[]){ 0x11, 0x22, 0x33, 0x44 }, sizeof(seed)));

	printf("SUMMARY assertions=%d failures=%d\n", 6, failures);
	return failures ? 1 : 0;
}
