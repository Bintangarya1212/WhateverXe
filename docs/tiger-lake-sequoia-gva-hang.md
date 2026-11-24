# Tiger Lake (Gen12 LP) GVA/VP hang on macOS Sequoia — notes and working setup

This document records a reproducible AppleGVA video-processing hang on Tiger
Lake-U, the flags this branch adds, and the configuration that is stable on the
test machine. It is a per-machine report, not upstream documentation.

## Test machine

- Lenovo ThinkPad T14 Gen 2, Core i7-1185G7, Intel Iris Xe `8086:9A49` (Gen12 LP)
- Internal eDP 1920x1080, no discrete GPU
- macOS Sequoia 15.8.3 (24H241), OpenCore
- WhateverXe 0.8.3 + WhateverXe Graphics 0.4.4

## Symptom

- Intermittent compositor freeze while the hardware cursor keeps moving.
- Video calls with the camera and screen casting lag and freeze; ending the
  call and waiting makes the desktop smooth again. Sometimes a full panic and
  reboot instead.

## Root cause (evidence from `/Library/Logs/DiagnosticReports`)

A GPU hang report from a camera call:

```
Application:      VTEncoderXPCService        (VideoToolbox hardware encoder)
Processing hang for hardware context ID[116]
RCS Ring is:      - busy - in a batch buffer  <-- Appears hung
IPEHR = 0x7a000004
INSTDONE = 0xffdcffff   Not done = VFE, TSG0, CS
LastContextSwitchReason = ELEMENT_SWITCH | WAIT_ON_SEMAPHORE | WAIT_ON_SCANLINE
VCS0/VECS0: NOT enabled (idle)
```

The media batch that AppleGVA builds for video processing (VFE) is submitted to
the RCS and never completes. WindowServer then waits on the GPU completion and
the userspace watchdog reports the display not ready with surfaces stuck
`GPU Busy`.

Removing the AppleGVA registry keys stops it completely, which shows the engine
hang is in the GVA/VideoToolbox media path rather than the display or cursor
plane. The experiments below that try to keep hardware video did not fix it; the
real fix has to be in the driver's VP/VFE pipeline.

## Working boot arguments

Stable on the test machine:

```
keepsyms=1 -allow3d -disablegfxfirmware -igfxdvmt -applbklbeta
-s0ixd3 -revwifi -tgldmiclilu
-wex-tgl-stampfix -wex-tgl-gpurec -wex-tgl-no-posh -wex-nogva -wex-no-host-rps
```

- `-allow3d`, `-disablegfxfirmware` — required for Metal on this setup.
- `-igfxdvmt`, `-applbklbeta`, `-tgldmiclilu`, `-revwifi`, `-s0ixd3` — board /
  platform flags already present before these changes.
- `-wex-nogva` — removes the AppleGVA keys so VideoToolbox falls back to
  software. This is what makes camera calls and screen casting stable.
- `-wex-tgl-gpurec`, `-wex-tgl-stampfix` — recovery safety net: if any engine
  still hangs, the reset is repaired instead of panicking.
- `-wex-tgl-no-posh` — RCS contexts without POSH; keeps recovery state clean.
- `-wex-no-host-rps` — disables WhateverXe's host frequency hook. Without GuC,
  the hook can leave the GT marked busy at a high frequency while idle; on this
  machine this flag lowers idle package power by roughly 2–4 W.

`io=0x800` and `-s0ixacnortc` were dropped: the first is an IOKit debug flag and
the second is not a recognized S0ixStandby argument.

## Switches added by this branch (all default off)

| Switch | Effect |
| --- | --- |
| `-wex-nogva` | remove every AppleGVA registry key (software video) |
| `-wex-va-noenc` | remove only `IOGVAScaler`, `IOGVABGRAEnc`, `IOGVAHEVCEncodeCapabilities` |
| `-wex-va-vpfix` | page-in patch clearing the #81 VP output capability list |
| `-wex-va-vfeg12` | correct the VA VFE state builder (experimental) |
| `-wex-tgl-gpurec` | restore render reset-domain state after a GPU reset |
| `-wex-tgl-stampfix` | finish a hung request on an idle engine |
| `-wex-tgl-no-posh` | run RCS contexts without POSH |
| `-wex-tgl-nomc` | run without the CCS |
| `-wex-va-nullguard` | skip empty renderer slots in the VA plug-in |

Every switch is byte-qualified against the exact donor; when the binary does not
match it fails closed and reports `Ready = No` instead of patching.

## Experiments that did not fix the camera hang

- `-wex-va-vpfix`: the #81 list is patched (`WEXVAFixVP.patched = 1`) but the
  camera call still resets.
- `-wex-va-noenc`: the key mask is applied (decode keys still present) but the
  hang persists, and screen casting still lags.
- `-wex-va-vfeg12`: the VFE builder patch engages but the hang persists.

Conclusion: the hang lives in the shared VP/VFE media path, so partial GVA
disabling converges to `-wex-nogva`.

## Building the kext

Local:

```sh
python3 tools/build.py --release     # -> build/WhateverXe.kext
python3 tools/test.py
```

From GitHub Actions (`.github/workflows/ci.yml`): the workflow runs on pushes to
`main`, tags, pull requests and manual dispatch. To build a branch that is not
`main`, either open a pull request for it or run the workflow manually:

1. Actions -> CI -> Run workflow -> pick the branch.
2. Download the `Artifacts` artifact.
3. Take `WhateverXe.kext` from the RELEASE zip and copy it to
   `EFI/OC/Kexts/WhateverXe.kext`.

The kext built from this branch is the one verified on the test machine
(`WhateverXe.kext` binary SHA-256 `3ecae87e9362191d2100fb18741e8d3f6c6889eb29af876da47d1627090d8eac`).

## Attribution

- The teardown drain barrier is ported from starterakun08-tech (`#62`).
- The recovery / no-POSH / no-GVA switches come from SaqibAlMalik's
  `tgl-stability` tree (`#109`).
