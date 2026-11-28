#!/usr/bin/env python3
"""Replay the production accelerator start with registry and donor mocks."""

from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "WhateverXe/kern_xe.cpp").read_text()


def extract(signature):
    return re.search(r"^" + re.escape(signature) + r".*?^}", source, re.M | re.S).group()


fixture = r"""
#include <cassert>
#include <cstring>
#include <map>
#include <new>
#include <string>
#include "kern_xelp_platform.hpp"
#include "kern_xelp_os.hpp"

struct OSObject { virtual ~OSObject() = default; };
struct OSNumber : OSObject {
    uint32_t value {};
    uint32_t unsigned32BitValue() const { return value; }
    static OSNumber *withNumber(unsigned, unsigned) { return nullptr; }
    void release() {}
};
struct OSDictionary : OSObject {
    static OSDictionary *withDictionary(OSDictionary *) { return nullptr; }
    void setObject(const char *, OSNumber *) {}
    void release() {}
};
struct IOService : OSObject {
    std::map<std::string, OSObject *> properties;
    OSNumber number;
    std::string decode;
    std::string retainedKey;
    OSObject *getProperty(const char *key) const {
        const auto it = properties.find(key);
        return it == properties.end() ? nullptr : it->second;
    }
    void removeProperty(const char *key) {
        if (retainedKey != key) properties.erase(key);
    }
    void setProperty(const char *key, uint32_t value, unsigned) {
        number.value = value;
        properties[key] = &number;
    }
    void setProperty(const char *key, const char *value) {
        decode = value;
        properties[key] = &number;
    }
    void setProperty(const char *, OSObject *) {}
    void release() {}
};
struct IOPCIDevice : IOService {
    XELP::Profile profile;
    IOPCIDevice *getDeviceMemoryWithRegister(unsigned) { return nullptr; }
    uint64_t getLength() const { return 0; }
    void setProperty(const char *, bool) {}
};
namespace XELP {
Profile deviceProfile(IOPCIDevice *pci) { return pci->profile; }
}
struct IORegistryEntry {
    static IORegistryEntry *getRegistryRoot() {
        static IORegistryEntry root;
        return &root;
    }
    std::map<std::string, bool> flags;
    void setProperty(const char *key, bool value) { flags[key] = value; }
    void setProperty(const char *, uint64_t, unsigned) {}
};
struct OSSerializer : OSObject {
    template<class... Args> static OSSerializer *forTarget(Args...) { return nullptr; }
    void release() {}
};
#define OSDynamicCast(Type, value) dynamic_cast<Type *>(value)
#define FunctionCast(function, pointer) reinterpret_cast<decltype(&function)>(pointer)
#define SYSLOG(...) ((void)0)

static IOPCIDevice *xelpSelectedGPU;
static XELP::Profile xelpSelectedProfile;
static bool enabled;
static const char *version;
static bool checkKernelArgument(const char *arg) {
    return enabled && !std::strcmp(arg, "-wex-nogva");
}
static bool xelpDisplay13RenderDevice(IOPCIDevice *) { return false; }
static bool adlnNativeRCSProfileRequested, adlnNativeRCSProfileReady;
static bool adlnQueueTraceEnabled, tglAlderLakeNContextPublishEnabled;
static int tglIRQLiveSerialize, tglSubmitCaptureSerialize, tglAlderLakeNContextPublishSerialize;
static int tglFaultSerialize, adlnQueueTraceSerialize, adlnQueueMemorySerialize, tglExecutionSerialize;
static uint64_t scratchSize;
static uint64_t *tglBlitScratchSize = &scratchSize;
static struct {
    IOService *startingOwner, *owner;
    bool captureStarted;
    uintptr_t startThread;
    uint64_t startupDone, startupEnd, barSize;
} tglHost;
static uintptr_t current_thread() { return 0; }
static void tglHostPublish() {}
static void tglHostClock(uint64_t *) {}
static void adlnRunKernelContextTrial(IOService *) {}
template<class... Args> void tglRecordStartOrder(Args...) {}
template<class... Args> void tglObserveAccelerator(Args...) {}

struct XE {
    bool tglGT2Detected, tglGT2Ready, display12SmallGTDetected, display12SmallGTReady;
    bool adlsDisplaySelected, adlsDisplayHooksReady, adlsBootConsumersFailed;
    bool adlnDetected, adlnNativeReady, adlnParentBoundaryReady, tglAcceleratorReady;
    IOService *tglAcceleratorOwner;
    uint64_t tglAcceleratorBARSize;
    uintptr_t orgTGLAcceleratorStart;
    static XE *callbackXE;
    static bool wrapTGLAcceleratorStart(IOService *, IOService *);
    static bool startAlderLakeNParentBoundary(IOService *, IOService *) { return false; }
};
XE *XE::callbackXE;

// The advertised properties match the recorded fork workaround.
static const char *const videoKeys[] {
    "IODVDBundleName", "IOVARendererID", "IOGVAHEVCDecode",
    "IOGVAHEVCEncodeCapabilities", "IOGVAHEVCDecodeCapabilities",
    "IOGVABGRAEnc", "IOGVAScaler", "IOGVACodec"
};
static OSObject marker;
static OSDictionary decodeCaps;
static unsigned calls;
static bool expectFallback, nativeResult;
static const char *stickyKey;
static bool nativeStart(IOService *service, IOService *) {
    ++calls;
    assert(service->getProperty("MetalMarker") == &marker);
    if (expectFallback) {
        for (const auto key : videoKeys) assert(!service->getProperty(key));
        for (const auto key : videoKeys) service->properties[key] = &marker;
        service->retainedKey = stickyKey;
    } else {
        for (const auto key : videoKeys) assert(service->getProperty(key));
        assert(service->number.value == 0x1080080 && service->decode == "2");
    }
    return nativeResult;
}

// PRODUCTION

int main() {
    const char *sequoia = "Darwin Kernel Version 24.6.0: test; root:xnu-test/RELEASE_X86_64";
    const char *tahoe = "Darwin Kernel Version 25.6.0: test; root:xnu-test/RELEASE_X86_64";
    const uint32_t target = 0x9A498086, other = 0x9A408086, alderLake = 0x46A68086;
    struct Case {
        bool arg, supportedOS;
        uint32_t physical, effective;
        bool sameProvider, fallback, nativeOK;
        const char *retainedKey;
    };
    const Case cases[] {
        {true,  true,  target,    target,    true,  true,  true,  ""},
        {true,  true,  target,    target,    true,  true,  false, ""},
        {true,  true,  target,    target,    true,  true,  true,  "IOGVACodec"},
        {false, true,  target,    target,    true,  false, true,  ""},
        {true,  false, target,    target,    true,  false, true,  ""},
        {true,  true,  other,     other,     true,  false, true,  ""},
        {true,  true,  alderLake, target,    true,  false, true,  ""},
        {true,  true,  target,    other,     true,  false, true,  ""},
        {true,  true,  target,    target,    false, false, true,  ""},
    };
    for (const auto &item : cases) {
        IOPCIDevice selected, provider;
        selected.profile = XELP::identify(item.physical, 1, item.effective);
        provider.profile = selected.profile;
        auto *actualProvider = item.sameProvider ? &selected : &provider;
        xelpSelectedGPU = &selected;
        xelpSelectedProfile = selected.profile;
        version = item.supportedOS ? sequoia : tahoe;
        enabled = item.arg;
        expectFallback = item.fallback;
        nativeResult = item.nativeOK;
        stickyKey = item.retainedKey;
        calls = 0;
        scratchSize = 0xD240;
        auto &flags = IORegistryEntry::getRegistryRoot()->flags;
        flags.clear();
        XE xe {};
        xe.tglAcceleratorReady = true;
        xe.orgTGLAcceleratorStart = reinterpret_cast<uintptr_t>(&nativeStart);
        XE::callbackXE = &xe;
        alignas(IOService) unsigned char storage[0x1500] {};
        new (storage + 0x1474) uint32_t {};
        auto *accelerator = new (storage) IOService;
        accelerator->properties["MetalMarker"] = &marker;
        for (const auto key : videoKeys) accelerator->properties[key] = &marker;
        if (!item.fallback) accelerator->properties.erase("IOGVAHEVCDecode");
        accelerator->properties["IOGVAHEVCDecodeCapabilities"] = &decodeCaps;
        accelerator->setProperty("IOVARendererID", 0x1080040, 32);
        assert(XE::wrapTGLAcceleratorStart(accelerator, actualProvider) == item.nativeOK);
        assert(calls == 1 && scratchSize == 0xE000);
        assert(accelerator->getProperty("MetalMarker") == &marker);
        for (const auto key : videoKeys) {
            const bool present = accelerator->getProperty(key);
            assert(present == (!item.fallback || !std::strcmp(key, item.retainedKey)));
        }
        if (item.fallback)
            assert(flags.at("WEXNoGVAReady") == (item.nativeOK && !*item.retainedKey));
        else
            assert(!flags.count("WEXNoGVAReady"));
        accelerator->~IOService();
    }
}
"""

production = "\n".join(extract(signature) for signature in (
    "static bool xelpSelectedDevice(",
    "static bool tglRemoveHardwareVideoProperties(",
    "bool XE::wrapTGLAcceleratorStart(",
))
with tempfile.TemporaryDirectory(prefix="wex-tgl-software-video-") as directory:
    directory = Path(directory)
    test = directory / "test.cpp"
    binary = directory / "test"
    test.write_text(fixture.replace("// PRODUCTION", production))
    subprocess.run(["clang++", "-std=c++17", "-I", str(root / "WhateverXe"),
                    str(test), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
