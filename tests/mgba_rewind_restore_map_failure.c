#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <mgba/core/rewind.h>
#include <mgba/core/serialize.h>
#include <mgba-util/patch/fast.h>
#include <mgba-util/vfs.h>

static int failures;
static size_t map_calls;
static size_t unmap_calls;
static size_t close_calls;
static size_t apply_calls;
static size_t load_calls;
static bool fail_next_current_map;
static bool apply_saw_null;
static bool load_state_result;
static void* (*current_map)(struct VFile*, size_t, int);
static void (*previous_unmap)(struct VFile*, void*, size_t);
static void (*current_unmap)(struct VFile*, void*, size_t);
static bool (*previous_close)(struct VFile*);
static bool (*current_close)(struct VFile*);

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	UNUSED(vf);
	UNUSED(buffer);
	UNUSED(size);
	return -1;
}

bool mCoreLoadStateNamed(struct mCore* core, struct VFile* vf, int flags) {
	UNUSED(core);
	UNUSED(vf);
	UNUSED(flags);
	++load_calls;
	return load_state_result;
}

static void* tracked_map(struct VFile* vf, size_t size, int flags) {
	++map_calls;
	if (fail_next_current_map) {
		fail_next_current_map = false;
		return NULL;
	}
	return current_map(vf, size, flags);
}

static void tracked_previous_unmap(struct VFile* vf, void* memory, size_t size) {
	++unmap_calls;
	previous_unmap(vf, memory, size);
}

static void tracked_current_unmap(struct VFile* vf, void* memory, size_t size) {
	++unmap_calls;
	current_unmap(vf, memory, size);
}

static bool tracked_previous_close(struct VFile* vf) {
	++close_calls;
	return previous_close(vf);
}

static bool tracked_current_close(struct VFile* vf) {
	++close_calls;
	return current_close(vf);
}

static bool observe_apply(struct Patch* patch, const void* input, size_t input_size,
	void* output, size_t output_size) {
	UNUSED(patch);
	++apply_calls;
	apply_saw_null = !input || !output;
	if (!apply_saw_null && input_size == output_size) {
		memcpy(output, input, input_size);
		return true;
	}
	return false;
}

static void check(const char* label, bool condition) {
	printf("%s %s\n", condition ? "PASS" : "FAIL", label);
	if (!condition) {
		++failures;
	}
}

static void reset_observations(void) {
	map_calls = 0;
	unmap_calls = 0;
	close_calls = 0;
	apply_calls = 0;
	load_calls = 0;
	fail_next_current_map = false;
	apply_saw_null = false;
	load_state_result = false;
}

static bool initialize_context(struct mCoreRewindContext* context) {
	const uint8_t previous[4] = { 0x11, 0x22, 0x33, 0x44 };
	const uint8_t current[4] = { 0x55, 0x66, 0x77, 0x88 };
	memset(context, 0, sizeof(*context));
	mCoreRewindContextInit(context, 1, false);
	if (!context->previousState || !context->currentState) {
		return false;
	}
	context->previousState->truncate(context->previousState, sizeof(previous));
	context->currentState->truncate(context->currentState, sizeof(current));
	if (context->previousState->write(context->previousState, previous, sizeof(previous))
			!= sizeof(previous)
		|| context->currentState->write(context->currentState, current, sizeof(current))
			!= sizeof(current)) {
		return false;
	}
	struct PatchFast* patch = mCoreRewindPatchesGetPointer(&context->patchMemory, 0);
	patch->d.applyPatch = observe_apply;
	context->size = 2;
	context->current = 0;
	return true;
}

static void instrument_context(struct mCoreRewindContext* context, bool inject_map_failure) {
	current_map = context->currentState->map;
	context->currentState->map = tracked_map;
	previous_unmap = context->previousState->unmap;
	current_unmap = context->currentState->unmap;
	context->previousState->unmap = tracked_previous_unmap;
	context->currentState->unmap = tracked_current_unmap;
	previous_close = context->previousState->close;
	current_close = context->currentState->close;
	context->previousState->close = tracked_previous_close;
	context->currentState->close = tracked_current_close;
	fail_next_current_map = inject_map_failure;
}

static void deinitialize_context(struct mCoreRewindContext* context) {
	mCoreRewindContextDeinit(context);
}

int main(void) {
	struct mCoreRewindContext context;
	bool restored;

	puts("SCOPE unchanged pinned rewind.c, patch-fast.c, memory.c, and vfs-mem.c; mCoreRewindRestore executes; map-failure adapter, patch observer, and core-load callback are test doubles");

	reset_observations();
	check("positive rewind context initializes", initialize_context(&context));
	instrument_context(&context, false);
	restored = mCoreRewindRestore(&context, NULL, 1);
	check("valid mappings reach patch callback and both unmaps",
		restored && map_calls == 1 && apply_calls == 1 && !apply_saw_null
		&& unmap_calls == 2 && load_calls == 1);
	deinitialize_context(&context);
	check("positive rewind teardown closes both state VFiles",
		close_calls == 2 && !context.previousState && !context.currentState);

	reset_observations();
	check("fault rewind context initializes", initialize_context(&context));
	instrument_context(&context, true);
	restored = mCoreRewindRestore(&context, NULL, 1);
	check("failed map reaches patch callback and both unmaps still run",
		restored && map_calls == 1 && apply_calls == 1 && apply_saw_null
		&& unmap_calls == 2 && load_calls == 1);
	check("restore returns true and consumes the entry after map failure",
		restored && context.size == 1 && context.current == 0);
	deinitialize_context(&context);
	check("fault rewind teardown closes both state VFiles",
		close_calls == 2 && !context.previousState && !context.currentState);

	reset_observations();
	check("recovery control context initializes", initialize_context(&context));
	instrument_context(&context, false);
	restored = mCoreRewindRestore(&context, NULL, 1);
	check("fresh valid restore succeeds after the injected-failure case",
		restored && map_calls == 1 && apply_calls == 1 && !apply_saw_null
		&& unmap_calls == 2 && load_calls == 1);
	deinitialize_context(&context);
	check("recovery control teardown closes both state VFiles",
		close_calls == 2 && !context.previousState && !context.currentState);

	printf("SUMMARY assertions=%d failures=%d\n", 10, failures);
	return failures ? 1 : 0;
}
