#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

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
	uint8_t guarded[6] = { 0xA5, 0x10, 0x11, 0x12, 0x13, 0x5A };
	uint8_t* borrowed = &guarded[1];
	uint8_t byte = 0;
	uint8_t pair[2] = { 0, 0 };
	struct VFile* vf = VFileFromMemory(borrowed, 4);
	ssize_t read_count;

	puts("SCOPE unchanged pinned vfs-mem.c; borrowed-memory non-expanding seek bounds and cursor preservation; GBA caller not executed");
	check("constructor exposes only the four-byte borrowed extent",
		vf && vf->size(vf) == 4 && vf->map(vf, 4, MAP_READ) == borrowed);
	if (!vf) {
		puts("SUMMARY assertions=8 failures=1");
		return 1;
	}

	check("valid absolute seek reads from the requested offset",
		vf->seek(vf, 2, SEEK_SET) == 2
		&& (read_count = vf->read(vf, pair, sizeof(pair))) == 2
		&& pair[0] == 0x12 && pair[1] == 0x13);

	check("relative underflow is rejected without changing the cursor",
		vf->seek(vf, 2, SEEK_SET) == 2
		&& vf->seek(vf, -3, SEEK_CUR) == -1
		&& (read_count = vf->read(vf, &byte, 1)) == 1 && byte == 0x12);

	check("valid negative end-relative seek remains inside the extent",
		vf->seek(vf, -1, SEEK_END) == 3
		&& (read_count = vf->read(vf, &byte, 1)) == 1 && byte == 0x13);

	check("end-relative underflow is rejected without changing the cursor",
		vf->seek(vf, 1, SEEK_SET) == 1
		&& vf->seek(vf, -5, SEEK_END) == -1
		&& (read_count = vf->read(vf, &byte, 1)) == 1 && byte == 0x11);

	check("negative absolute seek is rejected without changing the cursor",
		vf->seek(vf, 2, SEEK_SET) == 2
		&& vf->seek(vf, -1, SEEK_SET) == -1
		&& (read_count = vf->read(vf, &byte, 1)) == 1 && byte == 0x12);

	check("invalid whence is rejected without changing the cursor",
		vf->seek(vf, 1, SEEK_SET) == 1
		&& vf->seek(vf, 0, 99) == -1
		&& (read_count = vf->read(vf, &byte, 1)) == 1 && byte == 0x11);

	check("valid negative relative seek and all rejected seeks preserve guards and extent",
		vf->seek(vf, 3, SEEK_SET) == 3
		&& vf->seek(vf, -2, SEEK_CUR) == 1
		&& vf->size(vf) == 4 && guarded[0] == 0xA5 && guarded[5] == 0x5A);

	vf->close(vf);
	printf("SUMMARY assertions=%d failures=%d\n", 8, failures);
	return failures ? 1 : 0;
}
