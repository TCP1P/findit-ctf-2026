#include <unicorn/unicorn.h>
#include <iostream>
#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <sys/mman.h>

#define ADDRESS 0x1000000
#define STACK_ADDR 0x8000000
#define STACK_SIZE 2 * 1024 * 1024
#define ALLOWED_RUNNER /*CHANGEME*/

struct ArchConfig {
    uc_arch arch;
    uc_mode mode;
    int reg_syscall_nr;
    int reg_arg0;
    int reg_sp;
    int sys_execve_nr;
    std::vector<uint8_t> opcode;
};

struct SimulationContext {
    ArchConfig* config;
    bool is_valid;
};

static void hook_code(uc_engine *uc, uint64_t address, uint32_t size, void *user_data) {
    SimulationContext *ctx = (SimulationContext *)user_data;
    ArchConfig *cfg = ctx->config;

    uint8_t code[4] = {0};
    if (uc_mem_read(uc, address, code, cfg->opcode.size()) != UC_ERR_OK) {
        return;
    }

    for (size_t i = 0; i < cfg->opcode.size(); i++) {
        if (code[i] != cfg->opcode[i]) {
            return;
        }
    }

    uint64_t syscall_nr = 0;
    if (uc_reg_read(uc, cfg->reg_syscall_nr, &syscall_nr) != UC_ERR_OK) {
        ctx->is_valid = false;
        uc_emu_stop(uc);
        return;
    }

    bool blocked = false;
    if (cfg->arch == UC_ARCH_X86) {
        for (int sc : {41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,288,299,307,322,78,217}) {
            if (syscall_nr == (uint64_t)sc) { blocked = true; break; }
        }
    } else if (cfg->arch == UC_ARCH_ARM64 || cfg->arch == UC_ARCH_RISCV) {
        for (int sc : {198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,242,243,269,281,61}) {
            if (syscall_nr == (uint64_t)sc) { blocked = true; break; }
        }
    } else if (cfg->arch == UC_ARCH_MIPS) {
        for (int sc : {5040,5041,5042,5043,5044,5045,5046,5047,5048,5049,5050,5051,5052,5053,5054,5316,5217,5076}) {
            if (syscall_nr == (uint64_t)sc) { blocked = true; break; }
        }
    }

    if (blocked) {
        ctx->is_valid = false;
        uc_emu_stop(uc);
        return;
    }

    if (syscall_nr == (uint64_t)cfg->sys_execve_nr) {
        uint64_t arg0 = 0;
        if (uc_reg_read(uc, cfg->reg_arg0, &arg0) != UC_ERR_OK) {
            ctx->is_valid = false;
            uc_emu_stop(uc);
            return;
        }

        std::string filename;
        filename.reserve(64);
        for (size_t i = 0; i < 255; ++i) {
            uint8_t c = 0;
            if (uc_mem_read(uc, arg0 + i, &c, 1) != UC_ERR_OK) break;
            if (c == 0) break;
            filename.push_back((char)c);
        }

        if (filename != ALLOWED_RUNNER) {
            ctx->is_valid = false;
        }
        uc_emu_stop(uc);
    }
}

int main(int argc, char **argv) {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string hex_code;
    if (!std::getline(std::cin, hex_code)) {
        return 1;
    }

    std::vector<uint8_t> code;
    for (size_t i = 0; i < hex_code.length(); i += 2) {
        std::string b = hex_code.substr(i, 2);
        code.push_back((uint8_t)strtol(b.c_str(), NULL, 16));
    }

    ArchConfig x64 = {
        UC_ARCH_X86, UC_MODE_64,
        UC_X86_REG_RAX, UC_X86_REG_RDI, UC_X86_REG_RSP,
        59, {0x0f, 0x05}
    };
    ArchConfig arm64 = {
        UC_ARCH_ARM64, UC_MODE_ARM,
        UC_ARM64_REG_X8, UC_ARM64_REG_X0, UC_ARM64_REG_SP,
        221, {0x01, 0x00, 0x00, 0xd4}
    };
    ArchConfig riscv64 = {
        UC_ARCH_RISCV, UC_MODE_RISCV64,
        UC_RISCV_REG_A7, UC_RISCV_REG_A0, UC_RISCV_REG_SP,
        221, {0x73, 0x00, 0x00, 0x00}
    };
    ArchConfig mips64 = {
        UC_ARCH_MIPS, (uc_mode)(UC_MODE_MIPS64 | UC_MODE_BIG_ENDIAN),
        UC_MIPS_REG_V0, UC_MIPS_REG_A0, UC_MIPS_REG_SP,
        5057, {0x00, 0x00, 0x00, 0x0c}
    };

    SimulationContext ctx;
    ctx.is_valid = true;
#if defined(__x86_64__) || defined(_M_X64)
    ctx.config = &x64;
#elif defined(__aarch64__)
    ctx.config = &arm64;
#elif defined(__riscv) && __riscv_xlen == 64
    ctx.config = &riscv64;
#elif defined(__mips__) || defined(__mips64) || defined(__mips64__)
    ctx.config = &mips64;
#else
    return 1;
#endif

    uc_engine *uc;
    if (uc_open(ctx.config->arch, ctx.config->mode, &uc) != UC_ERR_OK) return 1;

    if (uc_mem_map(uc, ADDRESS, 2 * 1024 * 1024, UC_PROT_ALL) != UC_ERR_OK) { uc_close(uc); return 1; }
    if (uc_mem_map(uc, STACK_ADDR, STACK_SIZE, UC_PROT_ALL) != UC_ERR_OK) { uc_close(uc); return 1; }
    if (uc_mem_write(uc, ADDRESS, code.data(), code.size()) != UC_ERR_OK) { uc_close(uc); return 1; }

    uint64_t stack_start = STACK_ADDR + STACK_SIZE - 8;
    if (uc_reg_write(uc, ctx.config->reg_sp, &stack_start) != UC_ERR_OK) { uc_close(uc); return 1; }

    uc_hook trace;
    if (uc_hook_add(uc, &trace, UC_HOOK_CODE, (void *)hook_code, &ctx, 1, 0) != UC_ERR_OK) { uc_close(uc); return 1; }

    uc_emu_start(uc, ADDRESS, ADDRESS + code.size(), 0, 0);
    uc_close(uc);

    if (ctx.is_valid) {
        size_t mmap_size = (code.size() + (0x1000 - 1)) & ~(0x1000 - 1);
        void *mem = mmap(NULL, mmap_size,
                        PROT_READ | PROT_WRITE | PROT_EXEC,
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (mem == MAP_FAILED) return 1;

        memcpy(mem, code.data(), code.size());
        pid_t pid = fork();
        if (pid == 0) {
            auto fn = (void (*)())mem;
            fn();
            _exit(0);
        } else if (pid > 0) {
            int status;
            waitpid(pid, &status, 0);
        } else {
            return 1;
        }
    }

    return 0;
}