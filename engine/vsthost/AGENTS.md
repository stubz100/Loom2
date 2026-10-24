# engine/vsthost — loom2's own VST3 host (D127, AU3)

Verified at 5d08c74 on 2026-10-24.

A small C++ sidecar on Steinberg's MIT-licensed VST 3 SDK (pinned in `engine/vsthost.pin.json`). The orchestrator runs it once per request
through `orchestrator/loom2/vsthost.py`, in its job object; a plug-in that crashes ends that process, never loom2.

- **Build:** `python scripts/build_vsthost.py` fetches the SDK at the pin into `engine/tools/vst3sdk` (submodules base, cmake, pluginterfaces,
  public.sdk only), builds with CMake + Visual Studio 2022 (x64, Release, static runtime) into `engine/tools/vsthost-build`, and copies
  `loom2-vsthost.exe` and two of the SDK's sample effects (`again-sample-accurate`, `adelay`) into `engine/tools/vsthost/`. Nothing goes into
  the system's VST3 folders. `--check` (CI) holds the pin to this folder's source.
- **Commands** (one line of JSON each; see `engine/vsthost/src/main.cpp`): `paths`, `scan`, `params`, `state`, `render`, `editor`.
- **State files** are the host's own (`L2VS`, the component's state then the controller's); loom2 keeps them with a cut (AU4).
- **Rendering** is offline, 32-bit float, the main buses stereo (a mono plug-in is fed L+R and its output doubled), any side-chain off; a
  plug-in's reported latency is taken off so the output lines up with the input; the output is as long as the input.
- **The editor** is the plug-in's own view in a Win32 window; edits arrive through `IComponentHandler::performEdit` and reach the processor in
  one silent block before the state is saved. The process is not DPI-aware yet (Windows scales the window).
- **Tests:** the offline suite runs `orchestrator/tests/fake_vsthost.py` (never a built host); the rig runs
  `scripts/au_acceptance.py --parts host,editor` on the SDK's samples and one of the author's effects.
