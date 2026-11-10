"""Native R5 provider tests linked to the exact pinned mGBA source."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MGBA = ROOT / "upstream" / "mgba"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
ROM_BYTES = 32 * 1024 * 1024
RESOURCE_ID = "resource.test"
RESOURCE = b"native-resource-after-32MiB\x00"
PADDING_ID = "aaa.padding"
SOURCE_ID = "native-smoke"

import sys
sys.path.insert(0, str(TOOLS))

import xgba_resource_bridge as bridge_module
import xgba_resource_pack as packer
import xgba_resource_sidecar as sidecar


HARNESS = r"""
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/memory.h>
#include <mgba-util/vfs.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xgba_resource_mgba_adapter.c"

struct HostFixture {
    const char *path;
    const char *resource_id;
    uint64_t offset;
    uint64_t length;
    uint8_t digest[32];
    int truncate;
    unsigned lookup_calls;
    unsigned read_calls;
};

static int fixture_lookup(void *opaque, const char *id, uint64_t *length,
                          uint8_t digest[32])
{
    struct HostFixture *fixture = opaque;
    ++fixture->lookup_calls;
    if (strcmp(id, fixture->resource_id) != 0)
        return 1;
    *length = fixture->length;
    memcpy(digest, fixture->digest, 32);
    return 0;
}

static int fixture_read(void *opaque, const char *id, uint8_t *destination,
                        size_t capacity, size_t *bytes_read)
{
    struct HostFixture *fixture = opaque;
    ++fixture->read_calls;
    if (strcmp(id, fixture->resource_id) != 0 ||
        fixture->length > capacity)
        return 1;
    FILE *file = fopen(fixture->path, "rb");
    if (!file)
        return 1;
    if (fseeko(file, (off_t)fixture->offset, SEEK_SET) != 0) {
        fclose(file);
        return 1;
    }
    size_t requested = (size_t)fixture->length;
    if (fixture->truncate && requested)
        --requested;
    *bytes_read = fread(destination, 1, requested, file);
    int failed = ferror(file);
    fclose(file);
    return failed ? 1 : 0;
}

static void fail(const char *label)
{
    fprintf(stderr, "FAIL %s\n", label);
    exit(1);
}

static void make_rom(uint8_t *rom)
{
    memset(rom, 0, 32u * 1024u * 1024u);
    rom[0xAC] = 'X';
    rom[0x1200] = 0x00;
    rom[0x1201] = 0x00;
    rom[0x1202] = 0xA0;
    rom[0x1203] = 0xE1;
}

static int native_rom_smoke(const uint8_t *rom)
{
    struct mCore *core = GBACoreCreate();
    if (!core || !core->init(core))
        return 0;
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(rom, 32u * 1024u * 1024u);
    if (!vf || !core->loadROM(core, vf)) {
        if (vf)
            vf->close(vf);
        mCoreConfigDeinit(&core->config);
        core->deinit(core);
        return 0;
    }
    core->reset(core);
    uint32_t value = GBALoad32(core->cpu, GBA_BASE_ROM0 + 0x1200u, NULL);
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    return value == 0xE1A00000u;
}

int main(int argc, char **argv)
{
    if (argc != 5)
        fail("arguments");
    struct HostFixture fixture = {
        .path = argv[1],
        .resource_id = "resource.test",
        .offset = strtoull(argv[2], NULL, 10),
        .length = strtoull(argv[3], NULL, 10),
    };
    for (unsigned i = 0; i < 32; ++i) {
        unsigned value = 0;
        if (sscanf(argv[4] + i * 2, "%2x", &value) != 1)
            fail("digest_argument");
        fixture.digest[i] = (uint8_t)value;
    }
    if (fixture.offset <= 32u * 1024u * 1024u)
        fail("resource_not_beyond_32MiB");

    uint8_t *rom = malloc(32u * 1024u * 1024u);
    if (!rom)
        fail("ROM_allocation");
    make_rom(rom);
    uint8_t rom_digest[32];
    xgba_sha256(rom, 32u * 1024u * 1024u, rom_digest);

    struct XgbaMgbaProviderV1 host = {
        .abi_version = XGBA_MGBA_PROVIDER_ABI_VERSION,
        .struct_size = sizeof(struct XgbaMgbaProviderV1),
        .context = &fixture,
        .lookup = fixture_lookup,
        .read = fixture_read,
    };
    strcpy(host.source_id, "native-smoke");
    memcpy(host.source_sha256, rom_digest, sizeof(rom_digest));
    struct XgbaMgbaProvider provider;
    if (xgba_mgba_provider_open(&provider, &host, 1, "native-smoke",
                                rom_digest) != XGBA_MGBA_OK)
        fail("versioned_handshake");

    uint8_t output[128];
    memset(output, 0xA5, sizeof(output));
    size_t output_length = 0;
    if (xgba_mgba_provider_read(&provider, "resource.test", output,
                                sizeof(output), &output_length) != XGBA_MGBA_OK ||
        output_length != 28u ||
        memcmp(output, "native-resource-after-32MiB", 27u) != 0 ||
        output[27] != 0)
        fail("native_named_resource_read");

    struct XgbaMgbaProvider rejected;
    uint8_t wrong_identity[32];
    memcpy(wrong_identity, rom_digest, sizeof(wrong_identity));
    wrong_identity[0] ^= 1u;
    if (xgba_mgba_provider_open(&rejected, &host, 1, "native-smoke",
                                wrong_identity) != XGBA_MGBA_IDENTITY_MISMATCH ||
        fixture.lookup_calls != 1u)
        fail("source_identity_mismatch_refused");

    fixture.truncate = 1;
    memset(output, 0xA5, sizeof(output));
    output_length = 0;
    if (xgba_mgba_provider_read(&provider, "resource.test", output,
                                sizeof(output), &output_length) != XGBA_MGBA_TRUNCATED ||
        output_length != 0 || output[0] != 0xA5)
        fail("truncated_resource_refused_atomically");
    fixture.truncate = 0;
    fixture.digest[0] ^= 1u;
    if (xgba_mgba_provider_read(&provider, "resource.test", output,
                                sizeof(output), &output_length) != XGBA_MGBA_INTEGRITY_ERROR ||
        output_length != 0 || output[0] != 0xA5)
        fail("resource_digest_mismatch_refused");
    fixture.digest[0] ^= 1u;

    struct XgbaMgbaProvider disabled;
    if (xgba_mgba_provider_open(&disabled, &host, 0, NULL, NULL) != XGBA_MGBA_OK)
        fail("opt_out_handshake");
    unsigned lookups_before = fixture.lookup_calls;
    unsigned reads_before = fixture.read_calls;
    if (xgba_mgba_provider_read(&disabled, "resource.test", output,
                                sizeof(output), &output_length) != XGBA_MGBA_DISABLED ||
        fixture.lookup_calls != lookups_before ||
        fixture.read_calls != reads_before)
        fail("disabled_extension_has_no_host_calls");
    if (!native_rom_smoke(rom))
        fail("ordinary_native_ROM_route_without_extension");

    puts("PASS pinned_mgba_native_provider");
    puts("PASS resource_storage_beyond_32MiB");
    puts("PASS identity_mismatch_and_truncation_refused");
    puts("PASS disabled_extension_preserves_native_ROM_route");
    free(rom);
    return 0;
}
"""


class MgbaResourceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (MGBA / ".git").is_dir():
            raise RuntimeError(
                "BLOCKED: actual pinned mGBA checkout is absent at upstream/mgba"
            )
        revision = subprocess.run(
            ["git", "-C", str(MGBA), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if revision != PIN:
            raise RuntimeError(
                f"BLOCKED: upstream/mgba is {revision}, expected pinned {PIN}"
            )
        cls.temp = tempfile.TemporaryDirectory(prefix="xgba-mgba-provider-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.build_native_harness()

    @classmethod
    def build_native_harness(cls):
        root = Path(cls.temp.name)
        include_source = (TOOLS / "xgba_resource_mgba_adapter.c").as_posix()
        (root / "native_test.c").write_text(
            HARNESS.replace(
                '#include "xgba_resource_mgba_adapter.c"',
                f'#include "{include_source}"',
            ),
            encoding="utf-8",
        )
        (root / "CMakeLists.txt").write_text(
            f"""
cmake_minimum_required(VERSION 3.16)
project(XgbaMgbaNativeProvider C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(BUILD_QT OFF CACHE BOOL "" FORCE)
set(BUILD_SDL OFF CACHE BOOL "" FORCE)
set(BUILD_LIBRETRO OFF CACHE BOOL "" FORCE)
set(BUILD_TEST OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC ON CACHE BOOL "" FORCE)
set(BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(BUILD_HEADLESS OFF CACHE BOOL "" FORCE)
set(ENABLE_SCRIPTING OFF CACHE BOOL "" FORCE)
set(BUILD_PYTHON OFF CACHE BOOL "" FORCE)
set(USE_PNG OFF CACHE BOOL "" FORCE)
set(USE_ZLIB OFF CACHE BOOL "" FORCE)
set(ENABLE_GDB_STUB OFF CACHE BOOL "" FORCE)
add_subdirectory("{MGBA.as_posix()}" pinned-mgba)
add_executable(xgba_mgba_resource_provider_native native_test.c)
target_link_libraries(xgba_mgba_resource_provider_native PRIVATE mgba)
get_target_property(_mgba_defs mgba COMPILE_DEFINITIONS)
if(NOT _mgba_defs)
  message(FATAL_ERROR "Pinned mGBA compile definitions unavailable")
endif()
target_compile_definitions(xgba_mgba_resource_provider_native PRIVATE ${{_mgba_defs}})
target_include_directories(xgba_mgba_resource_provider_native PRIVATE
  "{MGBA.as_posix()}/include" "${{CMAKE_BINARY_DIR}}/pinned-mgba/include")
""",
            encoding="utf-8",
        )
        cls.build = root / "build"
        subprocess.run(
            ["cmake", "-S", str(root), "-B", str(cls.build), "-DCMAKE_BUILD_TYPE=Release"],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["cmake", "--build", str(cls.build), "--target",
             "xgba_mgba_resource_provider_native", "--parallel", "2"],
            check=True, capture_output=True, text=True,
        )
        cls.executable = cls.build / "xgba_mgba_resource_provider_native"

    def test_native_provider_uses_r1_r2_r3_resource_pipeline(self):
        with tempfile.TemporaryDirectory(prefix="xgba-resource-provider-") as directory:
            root = Path(directory)
            rom = bytearray(ROM_BYTES)
            rom[0xAC] = ord("X")
            rom[0x1200:0x1204] = b"\x00\x00\xa0\xe1"
            identity = {
                "id": SOURCE_ID,
                "sha256": hashlib.sha256(rom).hexdigest(),
            }
            source_data = root / "source.bin"
            manifest_path = root / "source.json"
            packed_manifest = root / "packed.json"
            resource_offset = ROM_BYTES + 4096
            with source_data.open("wb") as handle:
                handle.truncate(resource_offset + len(RESOURCE))
                handle.seek(resource_offset)
                handle.write(RESOURCE)
            manifest_path.write_text(json.dumps({
                "format": sidecar.FORMAT,
                "version": sidecar.VERSION,
                "source_identity": identity,
                "data_file": source_data.name,
                "resources": [
                    {
                        "id": RESOURCE_ID,
                        "offset": resource_offset,
                        "length": len(RESOURCE),
                        "sha256": hashlib.sha256(RESOURCE).hexdigest(),
                    },
                    {
                        "id": PADDING_ID,
                        "offset": 0,
                        "length": resource_offset,
                        "sha256": hashlib.sha256(bytes(resource_offset)).hexdigest(),
                    },
                ],
            }), encoding="utf-8")
            packer.build_pack([manifest_path], packed_manifest, identity)
            packed = sidecar.load_manifest(
                packed_manifest, expected_source_identity=identity
            )
            resource = packed.get_resource(RESOURCE_ID)
            self.assertGreater(resource.offset, ROM_BYTES)

            bridge = bridge_module.ResourceBridge(
                rom, identity, max_resource_bytes=1024, chunk_size=7
            )
            bridge.open(packed_manifest)
            self.assertEqual(bytes(bridge.stage(RESOURCE_ID)), RESOURCE)

            result = subprocess.run(
                [
                    str(self.executable),
                    str(packed.data_path),
                    str(resource.offset),
                    str(resource.length),
                    resource.sha256,
                ],
                check=True, capture_output=True, text=True,
            )
            self.assertIn("PASS pinned_mgba_native_provider", result.stdout)
            self.assertIn("PASS resource_storage_beyond_32MiB", result.stdout)
            self.assertIn("PASS identity_mismatch_and_truncation_refused", result.stdout)
            self.assertIn("PASS disabled_extension_preserves_native_ROM_route", result.stdout)


if __name__ == "__main__":
    unittest.main()
