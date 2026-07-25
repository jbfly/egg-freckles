# Zero-click Einstein package install and launch

Research date: 2026-07-26. The running image builds Einstein commit [`f5544a039fc3964e18b217ccffa030c6bf1e4044`](https://github.com/pguyot/Einstein/tree/f5544a039fc3964e18b217ccffa030c6bf1e4044) as the FLTK frontend (`containers/emulator.Dockerfile:3,35-48`).

## Bottom line

**No: the Einstein build already in `localhost/newton-harness-dev:round7b` has no supported zero-click host interface for installing and launching a package.** The necessary install and NewtonScript primitives are present, and a small local control socket exposing those two existing calls is the shortest complete fix; the apparent package-directory watcher, Toolkit, serial transports, and monitor do not provide an unattended Linux-host entry point in this FLTK build.

## 1. `TPlatformManager::InstallNewPackages`: real scanner, not a Linux watcher

### What it is

`InstallNewPackages()` scans a directory for regular files ending in `.pkg`, installs files newer than `.lastInstall`, and then touches `.lastInstall` ([`TPlatformManager.cpp:732-798`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Platform/TPlatformManager.cpp#L732-L798)). If no argument is supplied, it uses `mDocDir` ([lines 735-743](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Platform/TPlatformManager.cpp#L735-L743)). NewtonOS calls it once at the first power-on pause; the source calls this an iOS/iPhone/Android hack ([`TNativePrimitives.cpp:835-856`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/TNativePrimitives.cpp#L835-L856)). There is no filesystem watch or polling loop.

`mDocDir` is assigned through `SetDocDir()` ([`TPlatformManager.cpp:810-818`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Platform/TPlatformManager.cpp#L810-L818)). At this commit, callers exist only in the iOS frontend ([`iEinsteinViewController.mm:400-412`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/iEinstein/Classes/iEinsteinViewController.mm#L400-L412)) and Android frontend ([`TAndroidNativeApp.cpp:305-311`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/TAndroidNativeApp.cpp#L305-L311)). FLTK has no caller.

### Does it work in our build?

The scanner code is compiled, but it is inert: FLTK leaves `mDocDir` null, so the boot-time call logs “No package directory specified” and returns. There is no FLTK preference, environment variable, or command-line flag for this directory. `TFLSettings::loadPreferences()` reads ROM, flash, screen, memory, system, PCMCIA, and network settings, but no document/package directory ([`TFLSettings.cpp:235-305`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLSettings.cpp#L235-L305)).

The current `/packages` bind mount is also read-only. That would not prevent reading and installing packages, but it would prevent updating `.lastInstall`; enabling only `SetDocDir("/packages")` would therefore reinstall every visible package on every boot.

### How to invoke it

There is **no invocation in the current FLTK binary**. A source change could call:

```cpp
mPlatformManager->SetDocDir("/packages");
```

but that would provide only one boot-time scan, not runtime watching or app launch. It is not the recommended solution.

## 2. `TFLApp::InstallPackagesFromURI`: drag-and-drop handler, not IPC

### What it is

`InstallPackagesFromURI()` accepts newline-separated names. It URI-decodes each item, downloads `http://` or `https://` `.pkg` URLs, and otherwise passes the local path to `InstallPackage()` ([`TFLApp.cpp:508-585`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L508-L585)). Its normal FLTK entry point is a file dropped on the emulated screen: the `FL_PASTE` drag-and-drop event calls it with `Fl::event_text()` ([`TFLScreenManager.cpp:552-567`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Screen/TFLScreenManager.cpp#L552-L567)).

### Does it work in our build?

Yes when called from the process, but no non-GUI caller exists. `TFLApp::Run()` passes `argv` only to FLTK and the window ([`TFLApp.cpp:308-314,402-403`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L308-L314)); `InitFLTK()` delegates argument parsing to `Fl::args()` ([lines 1140-1148](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L1140-L1148)). A read-only local run of `einstein --help` printed only FLTK display/theme/window flags, then attempted to boot. There is no package-path argument, URI scheme registration, single-instance socket, D-Bus service, or environment variable.

### How to invoke it

Current supported invocation is GUI drag-and-drop or Einstein’s own package-selection UI. Neither meets the zero-click requirement. An X11 synthetic drag would still be GUI automation and is not recommended.

## 3. Built-in Einstein Toolkit: capable, but GUI-only

### What it is

The Toolkit is compiled into this binary: CMake defines `USE_TOOLKIT=1` when NEWT64 is present ([`CMakeLists.txt:595-614`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/CMakeLists.txt#L595-L614)). `TFLApp::UserActionShowToolkit()` creates and shows it only in response to the FLTK UI action ([`TFLApp.cpp:762-769`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L762-L769)).

The Toolkit can do everything needed internally:

- `UserActionRun()` builds, installs, and runs the current script ([`TToolkit.cpp:589-603`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Toolkit/TToolkit.cpp#L589-L603)).
- `AppBuild()` compiles the `.ns`, `.nscript`, or `.script` source with NEWT64 and writes a `.pkg` ([`TToolkit.cpp:983-1122`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Toolkit/TToolkit.cpp#L983-L1122)). The file chooser does not advertise `.newt`; it advertises `*.{ns,nscript,script}` ([`TToolkit.cpp:398-403`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Toolkit/TToolkit.cpp#L398-L403)).
- `AppInstall()` removes the old package and calls `InstallPackagesFromURI()` ([`TToolkit.cpp:1132-1151`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Toolkit/TToolkit.cpp#L1132-L1151)).
- `AppRun()` evaluates `GetRoot().|packageSymbol|:Open()` ([`TToolkit.cpp:1154-1168`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Toolkit/TToolkit.cpp#L1154-L1168)).

### Does it work in our build?

Yes interactively. It has no command-line mode, script-file startup argument, stdin reader, socket, or other host API. When first shown it loads the first recent file or the Hello World sample, then shows an FLTK window ([`TToolkit.cpp:232-287`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Toolkit/TToolkit.cpp#L232-L287)).

`TMainPlatformDriver::NewtonScriptCall()` is the reverse direction: NewtonScript running *inside NewtonOS* calls registered Einstein host functions through `Einstein.Platform` ([`TNewt.cpp:46-77`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Platform/TNewt.cpp#L46-L77)). It is not an external evaluator.

### How to invoke it

Only through the Toolkit menu/window and its Build/Install/Run controls. There is no non-interactive invocation in this build.

## 4. Serial, PTY, pipes, TCP, `tntk`, and UnixNPI

### What is compiled and enabled

Linux includes named-pipe, PTY, BasiliskII, and TCP-client serial drivers ([`TSerialPorts.cpp:176-203`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Serial/TSerialPorts.cpp#L176-L203)). The FLTK frontend currently hard-codes the external port to `kTcpClientDriver` and the other three ports to null; its own comment says preferences still need to be added ([`TFLApp.cpp:1261-1269`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L1261-L1269)). The TCP driver defaults to client address `127.0.0.1` and port `3679` ([`TSerialPortDriverTcpClient.cpp:82-93`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Serial/TSerialPortDriverTcpClient.cpp#L82-L93), [`TSerialPortDriverTcpClient.h:148-152`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Serial/TSerialPortDriverTcpClient.h#L148-L152)). Therefore the host-side Dock/Inspector server must listen on port 3679 **inside the container’s network namespace** unless code changes the address; port 3679 is not published by the current container.

There is also a newer native host-port path. FLTK registers PTY defaults such as `/tmp/einstein-extr.pty` ([`TFLApp.cpp:1271-1281`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L1271-L1281)). When Newton’s Einstein serial driver supplies the `eloc` option, the native primitive creates the selected host driver ([`TNativePrimitives.cpp:2064-2102`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/TNativePrimitives.cpp#L2064-L2102)); the PTY implementation creates a real pseudoterminal and symlinks the configured path to its slave ([`TSerialHostPortPTY.cpp:35-97`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Serial/TSerialHostPortPTY.cpp#L35-L97)). No `/tmp/einstein-*.pty` existed during read-only inspection, so the running Newton had not activated that path.

### Host tools

- **UnixNPI 1.1.3** opens `/dev/newton`, uploads an arbitrary `.pkg`, and is invoked as `unixnpi package.pkg`. Its README still requires opening Newton’s Dock application, selecting Serial, and tapping Connect ([source archive](https://www.unna.org/unna/unix/unixnpi-1.1.3.tar.gz)). It could use a PTY by symlinking `/dev/newton`, but it is not zero-click without Newton-side auto-connect.
- **The pinned `tntk`** can install its built project and send arbitrary NewtonScript over an Inspector connection. Its command loop sends ordinary lines as compiled code and `:d` as delete-plus-download ([`tntk.cpp:142-203`](https://github.com/ekoeppen/tntk/blob/f9f3f5dd2444997f1febd5648f60ec71a3a08afd/tntk.cpp#L142-L203)). However, although preferences parse `-t PORT` ([`preferences.cpp:78-115`](https://github.com/ekoeppen/tntk/blob/f9f3f5dd2444997f1febd5648f60ec71a3a08afd/preferences.cpp#L78-L115)), `TTntk::MRun()` unconditionally constructs `TDCLFDSerialPort` and never uses the parsed TCP setting ([`tntk.cpp:108-130`](https://github.com/ekoeppen/tntk/blob/f9f3f5dd2444997f1febd5648f60ec71a3a08afd/tntk.cpp#L108-L130)). Thus `-t` does not work in the image’s pinned build.

### Does this give zero-click operation?

No. A viable serial command after a Newton-side Inspector/Dock session exists would look like:

```sh
# Inside the container, after /tmp/einstein-extr.pty exists and Newton connects:
tntk -p /tmp/einstein-extr.pty -P /platforms app.nprj
# Then on tntk stdin:
:d
GetRoot().|AppSymbol:Developer|:Open();
:q
```

For UnixNPI, `/dev/newton` would point at the Einstein PTY and the command would be `unixnpi app.pkg`. Both still require installing/configuring a Newton-side transport and causing it to connect. That is more machinery than directly exposing Einstein’s already-existing install/evaluate calls.

## 5. Monitor/debugger: startup scripts, but no NewtonScript injection channel

### What it is

The FLTK preferences load `LaunchMonitorAtBoot` and `BreakAtROMBoot` ([`TFLSettings.cpp:263-285`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLSettings.cpp#L263-L285)). `LaunchMonitorAtBoot=1` only shows the monitor window; the code that would honor `BreakAtROMBoot` is commented out ([`TFLApp.cpp:410-415`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/TFLApp.cpp#L410-L415)).

The monitor automatically reads `/rom/717006.monitorrc` at startup ([`TMonitor.cpp:168-185,541-551`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Monitor/TMonitor.cpp#L168-L185)). Monitor scripts are lists of debugger commands: run/stop/step, breakpoints, register and memory reads/writes, state load/save, and nested `!filename` scripts ([`TMonitor.cpp:1388-1423`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Monitor/TMonitor.cpp#L1388-L1423)). There is no command to call `InstallPackage()` or `EvalNewtonScript()`.

The apparent monitor socket is an internal `socketpair` used for refresh notification, and it is compiled out for FLTK ([`TMonitor.cpp:126-134`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Monitor/TMonitor.cpp#L126-L134)). FLTK sends commands only from the monitor terminal widget callback ([`TFLMonitor.cpp:893-904`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Monitor/TFLMonitor.cpp#L893-L904)). It does not read stdin or listen on a public socket.

### Does it work for this goal?

No. It could theoretically patch emulator memory and registers, but that would be ROM-version-specific, unsafe, and much more work than exposing the supported package/event APIs.

### Important adjacent finding: the unbuilt CLI frontend

Einstein’s source still contains a CLI app whose stdin commands are exactly what is needed:

- `install path` calls `mPlatformManager->InstallPackage(path)`.
- `ns command` calls `mPlatformManager->EvalNewtonScript(command)`.

See [`TCLIApp.cpp:657-752`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/TCLIApp.cpp#L657-L752) and its help text at [lines 755-772](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/TCLIApp.cpp#L755-L772). The CLI also has `--serial=tcp:server:port` ([lines 294-303,395-429](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/TCLIApp.cpp#L294-L303)).

This does **not** work in our binary. Current CMake explicitly builds only the FLTK or SDL frontend ([`app/CMakeLists.txt:1-11`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/CMakeLists.txt#L1-L11)); the FLTK source list contains `TFLApp.cpp`, not `TCLIApp.cpp` ([`app/FLTK/CMakeLists.txt:12-21`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/FLTK/CMakeLists.txt#L12-L21)).

## Prior art

- **Einstein’s macOS AppleScript bridge is the closest proven solution.** The Cocoa frontend directly exposes package install and NewtonScript evaluation ([`TCocoaAppController.mm:571-593`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/app/TCocoaAppController.mm#L571-L593)); the manual documents that macOS Einstein is scriptable ([manual lines 218-220](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Documentation/UserManual.html#L218-L220)). Linux FLTK lacks the equivalent bridge.
- **Eckhart Köppen automated the edit/build/install loop with Einstein, TextMate, `tntk`, and AppleScript.** His script closes the running app, removes its package, and calls `install package`; adding `GetRoot().|symbol|:Open()` would launch it. <https://40hz.org/Pages/mottek/2011/2011-01-16/>
- **Android users observed the document-directory scanner in practice.** A NewtonTalk report says restarting Android Einstein brought back flash state and “updates with new packages in the Einstein folder,” matching `SetDocDir()` plus the first-pause scan. <http://www.newtontalk.net/archive/newtontalk/2021-April/000689.html>
- **Matthias Melcher documented Einstein serial emulation and direct NCX connectivity**, with a stated goal of edit, compile, upload, and run from a developer environment. His documented Dock flow still requires opening Dock and tapping Connect. <http://matthiasm.com/software/einstein>
- **UnixNPI and `lpkg` are prior command-line package uploaders**, but both depend on a Newton-side Dock/Connection session. Sources and notes: <https://www.unna.org/unna/unix/unixnpi-1.1.3.tar.gz> and <https://www.unna.org/unna/unix/lpkg.tar.gz>.
- **No Linux FLTK automation socket, headless package-install CI project, or hidden package-directory preference was found** in Einstein’s docs, GitHub issues/pull requests, NewtonTalk results, or broader Brave searches.

## Recommended plan

The shortest complete path is to copy the proven Cocoa/CLI idea into FLTK as a tiny local IPC surface. Do not build a Dock client and do not automate the GUI.

1. **Add a Unix-domain control socket to the FLTK process**, for example `/state/einstein-control.sock`. Keep it inside the existing state volume and mode it `0600`.
2. **Expose only two line commands**, directly reusing existing methods:

   ```text
   install /packages/harness-loader/harness-loader.pkg
   ns GetRoot().|-HarnessLoaderR14G:jbfly|:Open();
   ```

   `install` calls `TPlatformManager::InstallPackage(path)`; `ns` calls `TPlatformManager::EvalNewtonScript(code)`. Validate install paths to the `/packages/` tree and cap command/package sizes.
3. **Integrate the socket with FLTK’s event loop** using `Fl::add_fd`, so calls run on the same process/UI thread rather than racing the emulator from the separate Python `emulator-control` process.
4. **Add two small endpoints or one passthrough endpoint to `emulator-control`** only after the socket works. The Python service writes to the local socket; it does not reimplement Newton package or Dock protocols.
5. **Invoke from the host** with concrete commands such as:

   ```sh
   curl -fsS -X POST http://127.0.0.1:18080/install \
     --data-binary '/packages/harness-loader/harness-loader.pkg'

   curl -fsS -X POST http://127.0.0.1:18080/newtonscript \
     --data-binary 'GetRoot().|-HarnessLoaderR14G:jbfly|:Open();'
   ```

6. **Return an accepted/queued result, not a false synchronous success.** Einstein’s install and NewtonScript methods enqueue Newton events ([`TPlatformManager.cpp:640-689`](https://github.com/pguyot/Einstein/blob/f5544a039fc3964e18b217ccffa030c6bf1e4044/Emulator/Platform/TPlatformManager.cpp#L640-L689)); they do not report NewtonOS completion. Verification should use existing flash/package evidence or an app-specific readiness signal.

For package-specific launch, use the package’s known root symbol. The current examples already have stable symbols; for an arbitrary third-party package, inspect its project/source or package metadata before issuing `GetRoot().|symbol|:Open()`.

## What would need building

| Option | Delivers | Rough effort | Recommendation |
|---|---|---:|---|
| FLTK Unix socket plus thin HTTP forwarding | Runtime install and NewtonScript launch from host | 0.5–1 day, including validation and one integration test | **Build this** |
| Set `mDocDir` and make `/packages` writable | Boot-time install only; no watch, no launch | 1–2 hours | Skip; incomplete and reinstalls are awkward |
| Restore a supported CLI CMake target and adjust container lifecycle/stdin | Scriptable `install` and `ns`; potentially headless | 1–2 days because the current build system no longer targets `TCLIApp` | Useful later, not shortest |
| PTY/TCP plus UnixNPI, `tntk`, or cDCL and Newton-side auto-connect | Dock/Inspector install and evaluation | 2–4 days, plus transport/package setup | Skip unless Dock compatibility is itself a requirement |
| Monitor-based memory injection | Version-specific install/eval hack | Several days with high fragility | Do not build |

## Not verified

- I did not install a package or restart/reconfigure the running emulator, per the read-only constraint.
- I did not prove that the legacy `TCLIApp` still compiles at commit `f5544a0`; current CMake does not include a CLI target.
- I did not prove a Newton-side Inspector or Dock package in the current flash can auto-connect. No active Einstein PTY or TCP/3679 connection was present during inspection.
- I did not find a completion callback for `InstallPackage()` or `EvalNewtonScript()`; source inspection shows enqueue-only behavior, so an automation API must not claim completion without a separate acknowledgement mechanism.
