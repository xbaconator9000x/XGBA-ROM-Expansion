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
	uint8_t guarded[6] = { 0xA5, 0x10, 0x11, 0x12, 0x13, 0x5A };
	uint8_t* borrowed = &guarded[1];
	const uint8_t in_bounds[2] = { 0x21, 0x22 };
	const uint8_t boundary[2] = { 0x31, 0x32 };
	const uint8_t at_end = 0x41;
	struct VFile* vf = VFileFromMemory(borrowed, 4);
	ssize_t complete_write = -1;
	ssize_t partial_write = -1;
	ssize_t end_write = -1;
	bool closed = false;
	bool borrowed_survived_close = false;

	puts("SCOPE unchanged pinned vfs-mem.c; borrowed-memory VFile short-write and close ownership only; GBA caller not executed");
	check("constructor borrows bounded four-byte storage", vf && vf->size(vf) == 4
		&& vf->map(vf, 4, MAP_READ | MAP_WRITE) == borrowed);
	if (!vf) {
		puts("SUMMARY assertions=5 failures=1");
		return 1;
	}

	check("in-bounds write completes and updates borrowed bytes", vf->seek(vf, 1, SEEK_SET) == 1
		&& (complete_write = vf->write(vf, in_bounds, sizeof(in_bounds))) == 2
		&& borrowed[1] == 0x21 && borrowed[2] == 0x22 && vf->size(vf) == 4);
	check("boundary-crossing write reports a one-byte short write without touching guards",
		vf->seek(vf, 3, SEEK_SET) == 3
		&& (partial_write = vf->write(vf, boundary, sizeof(boundary))) == 1
		&& borrowed[3] == boundary[0] && vf->size(vf) == 4
		&& guarded[0] == 0xA5 && guarded[5] == 0x5A);
	check("write at borrowed-buffer end reports zero and does not grow",
		vf->seek(vf, 4, SEEK_SET) == 4
		&& (end_write = vf->write(vf, &at_end, sizeof(at_end))) == 0
		&& vf->size(vf) == 4 && guarded[0] == 0xA5 && guarded[5] == 0x5A);
	closed = vf->close(vf);
	borrowed_survived_close = guarded[0] == 0xA5 && guarded[1] == 0x10
		&& guarded[2] == 0x21 && guarded[3] == 0x22 && guarded[4] == 0x31
		&& guarded[5] == 0x5A;
	check("close returns true and leaves caller-owned storage intact",
		closed && borrowed_survived_close);

	printf("SUMMARY assertions=%d failures=%d complete_write=%zd boundary_write=%zd end_write=%zd\n",
		5, failures, complete_write, partial_write, end_write);
	return failures ? 1 : 0;
}
