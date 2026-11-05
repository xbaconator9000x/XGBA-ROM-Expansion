#include <mgba/internal/arm/arm.h>
#include <mgba/internal/arm/isa-inlines.h>

#include <stdint.h>
#include <stdio.h>

static uint32_t fetch[16];

static void set_region(struct ARMCore* cpu, uint32_t address) {
	(void) cpu;
	(void) address;
}

int main(void) {
	struct ARMCore cpu = { 0 };
	cpu.memory.activeRegion = fetch;
	cpu.memory.activeMask = sizeof(fetch) - 1;
	cpu.memory.setActiveRegion = set_region;
	cpu.executionMode = MODE_ARM;
	cpu.nextEvent = 100;
	cpu.gprs[0] = 4;

	if (!ARMTestCondition(&cpu, 0xF)) {
		return 1;
	}
	ARMRunFake(&cpu, 0xF3A00001u);
	ARMRun(&cpu);
	if (cpu.gprs[0] != 4) {
		return 2;
	}

	puts("ARM_NV_HOST_CONTROL_PASS predicate=TRUE cpu_effect=SKIPPED oracle=NONE");
	return 0;
}
