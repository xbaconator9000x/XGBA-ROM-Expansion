/* Guard-page witness for unchanged source-extracted pinned FireRed readers.
 * Test-only POSIX memory protection, NOT original GBA/mGBA safety behavior.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/wait.h>
typedef uint8_t u8;
typedef uint16_t u16;
static struct {u8 *mapScripts;} gMapHeader;
static u8 outer[] = {2, 0x80, 0, 0, 8, 0};
static u8 *guard_table;
static u8 *guard_begin;
static size_t page_size;
static int signal_pipe = -1;
static u16 VarGet(u16 value) { return value; }
static u16 read16(const u8 *p) { return (u16)(p[0] | ((u16)p[1] << 8)); }
static u8 *readptr(const u8 *p) {
    uint32_t value = (uint32_t)p[0] | ((uint32_t)p[1] << 8)
                   | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    if (value != 0x08000080u) _exit(45);
    return guard_table;
}
#define T1_READ_16(ptr) read16(ptr)
#define T2_READ_PTR(ptr) readptr(ptr)
#include "phase1_reader_functions.inc"

static void on_segv(int sig, siginfo_t *info, void *ctx) {
    (void)sig;
    (void)ctx;
    uintptr_t at = (uintptr_t)info->si_addr;
    uintptr_t lo = (uintptr_t)guard_begin;
    if (at >= lo && at < lo + page_size) {
        char marker = 'G';
        (void)write(signal_pipe, &marker, 1);
        _exit(90);
    }
    _exit(91);
}
static void child_case(int scenario, int fd) {
    long sz = sysconf(_SC_PAGESIZE);
    if (sz <= 0) _exit(41);
    page_size = (size_t)sz;
    u8 *pages = mmap(NULL, page_size * 2, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (pages == MAP_FAILED) _exit(42);
    guard_begin = pages + page_size;
    if (mprotect(guard_begin, page_size, PROT_NONE)) _exit(43);
    signal_pipe = fd;
    struct sigaction sa = {0};
    sa.sa_sigaction = on_segv;
    sa.sa_flags = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGSEGV, &sa, NULL)) _exit(44);
    if (scenario == 0 || scenario == 2) {
        /* One 5-byte nonmatching outer record; only case 0 has sentinel. */
        const u8 bytes[] = {3, 0, 0, 0, 8, 0};
        size_t n = scenario == 0 ? 6 : 5;
        u8 *start = guard_begin - n;
        for (size_t i = 0; i < n; i++) start[i] = bytes[i];
        gMapHeader.mapScripts = start;
        if (MapHeaderGetScriptTable(99) != NULL) _exit(46);
    } else {
        /* One 8-byte mismatching conditional record; only case 1 terminates. */
        const u8 bytes[] = {0, 0x40, 1, 0x40, 0, 0, 0, 8, 0, 0};
        size_t n = scenario == 1 ? 10 : 8;
        guard_table = guard_begin - n;
        for (size_t i = 0; i < n; i++) guard_table[i] = bytes[i];
        gMapHeader.mapScripts = outer;
        if (MapHeaderCheckScriptTable(2) != NULL) _exit(47);
    }
    _exit(0);
}
static void run_case(int scenario, const char *line) {
    int fds[2];
    if (pipe(fds)) { perror("pipe"); exit(1); }
    pid_t child = fork();
    if (child < 0) { perror("fork"); exit(1); }
    if (child == 0) {
        close(fds[0]);
        child_case(scenario, fds[1]);
    }
    close(fds[1]);
    int status = 0;
    if (waitpid(child, &status, 0) != child) { perror("waitpid"); exit(1); }
    char byte = 0;
    ssize_t count = read(fds[0], &byte, 1);
    close(fds[0]);
    int malformed = scenario >= 2;
    if (!WIFEXITED(status) ||
        WEXITSTATUS(status) != (malformed ? 90 : 0) ||
        count != (malformed ? 1 : 0) ||
        (malformed && byte != 'G')) {
        fprintf(stderr, "GUARD_CASE_FAIL scenario=%d status=%d count=%ld\n",
                scenario, status, (long)count);
        exit(1);
    }
    puts(line);
}
int main(void) {
    run_case(0, "OUTER_TERMINATED returns_null=1");
    run_case(1, "CONDITIONAL_TERMINATED returns_null=1");
    run_case(2, "OUTER_MISSING_SENTINEL guarded_fault=1");
    run_case(3, "CONDITIONAL_MISSING_SENTINEL guarded_fault=1");
    puts("HOST_PINNED_READER_GUARD_PAGE PASS cases=4 guarded_faults=2 gate=FAIL_INCOMPLETE approvals=0");
    return 0;
}
