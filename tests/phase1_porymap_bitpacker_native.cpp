#include "bitpacker.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
int main(int argc, char** argv) {
    if (argc != 2) return 91;
    if (!std::strcmp(argv[1], "small")) {
        BitPacker b(0x0fu);
        if (b.clamp(0x2au) != 0x0au || b.pack(0x0au) != 0x0au || b.unpack(0x0au) != 0x0au) return 92;
        std::puts("BITPACKER_POSITIVE_SMALL");
        return 0;
    }
    if (!std::strcmp(argv[1], "highbit")) {
        BitPacker b(0x80000000u);
        if (b.pack(1u) != 0x80000000u || b.unpack(0x80000000u) != 1u) return 93;
        std::puts("BITPACKER_POSITIVE_HIGHBIT");
        return 0;
    }
    if (!std::strcmp(argv[1], "allbits")) {
        BitPacker b(0xffffffffu);
        if (b.pack(0xdeadbeefu) != 0xdeadbeefu || b.unpack(0xdeadbeefu) != 0xdeadbeefu) return 94;
        std::puts("BITPACKER_POSITIVE_ALLBITS");
        return 0;
    }
    if (!std::strcmp(argv[1], "width31")) {
        BitPacker b(0x7fffffffu);
        std::printf("BITPACKER_WIDTH31_MAX=%u\n", b.maxValue());
        return 0;
    }
    return 95;
}
