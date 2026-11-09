#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

enum mPlatform {
	mPLATFORM_NONE,
	mPLATFORM_GBA,
	mPLATFORM_GB
};

struct VFile {};

struct mCore {
	int kind;
	void (*init)(mCore*);
	void (*deinit)(mCore*);
	size_t (*stateSize)(mCore*);
};

namespace QGBA {
struct SaveConverter {
	static mPlatform getStatePlatform(VFile*);
};
}

using namespace QGBA;

static constexpr uint32_t GBASavestateMagic = 0x01000000;
static constexpr uint32_t GBASavestateVersion = 0x0000000C;
static constexpr uint32_t GBSavestateMagic = 0x00000001;
static constexpr uint32_t GBSavestateVersion = 0x00000005;

#define M_CORE_GBA
#define M_CORE_GB
#define LOAD_32LE(value, offset, pointer) \
	do { \
		const auto* bytes = static_cast<const uint8_t*>(pointer) + (offset); \
		(value) = static_cast<uint32_t>(bytes[0]) | \
			(static_cast<uint32_t>(bytes[1]) << 8) | \
			(static_cast<uint32_t>(bytes[2]) << 16) | \
			(static_cast<uint32_t>(bytes[3]) << 24); \
	} while (0)

static int selectedCore;

static void mock_init(mCore*) {}

static void mock_deinit(mCore* core) {
	std::free(core);
}

static size_t mock_state_size(mCore*) {
	return 16;
}

static mCore* mock_core_create(int kind) {
	auto* core = static_cast<mCore*>(std::malloc(sizeof(mCore)));
	if (!core) {
		std::abort();
	}
	core->kind = kind;
	core->init = mock_init;
	core->deinit = mock_deinit;
	core->stateSize = mock_state_size;
	return core;
}

static mCore* GBACoreCreate() {
	return mock_core_create(mPLATFORM_GBA);
}

static mCore* GBCoreCreate() {
	return mock_core_create(mPLATFORM_GB);
}

static void* mCoreExtractState(mCore* core, VFile*, void*) {
	if (core->kind != selectedCore) {
		return nullptr;
	}
	return std::calloc(1, 16);
}

static void mappedMemoryFree(void* memory, size_t) {
	std::free(memory);
}

namespace QGBA {
PHASE1_INSERT_PINNED_GET_STATE_PLATFORM
}

int main(int argc, char** argv) {
	if (argc != 2) {
		return 2;
	}
	if (!std::strcmp(argv[1], "gba")) {
		selectedCore = mPLATFORM_GBA;
	} else if (!std::strcmp(argv[1], "gb")) {
		selectedCore = mPLATFORM_GB;
	} else if (!std::strcmp(argv[1], "null")) {
		selectedCore = 0;
	} else {
		return 2;
	}
	const mPlatform result = SaveConverter::getStatePlatform(nullptr);
	std::printf("PHASE1_CORE_LIFETIME_NULL_CONTROL platform=%d\n", result);
	return 0;
}
