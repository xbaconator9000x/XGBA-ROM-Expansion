/* Isolated pinned macro host UBSan probe; NOT a complete upstream build. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#define LOAD_32LE(DEST, ADDR, ARR) DEST = *(uint32_t*) ((uintptr_t) (ARR) + (size_t) (ADDR))
#define STORE_32LE(SRC, ADDR, ARR) *(uint32_t*) ((uintptr_t) (ARR) + (size_t) (ADDR)) = SRC
__attribute__((noinline)) static uint32_t pinned_load(void *p) { uint32_t v; LOAD_32LE(v,0,p); return v; }
__attribute__((noinline)) static void pinned_store(void *p) { STORE_32LE(0x44332211u,0,p); }
int main(int argc, char **argv) {
  (void)argv;
  uint32_t aligned[2] = {0x44332211u, 0};
  unsigned char *bytes = malloc(16);
  if (!bytes) return 2;
  for (int i=0;i<16;i++) bytes[i] = (unsigned char)(i + argc);
  if (argc == 1) printf("aligned=%08x\n", pinned_load(aligned));
  else if (argc == 2) { pinned_store(bytes+1); printf("store=%02x\n", bytes[1]); }
  else printf("load=%08x\n", pinned_load(bytes+1));
  free(bytes);
  return 0;
}
