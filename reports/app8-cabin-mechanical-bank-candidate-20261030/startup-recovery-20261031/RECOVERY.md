# MATLAB R2026a startup recovery investigation

Date: 2026-10-31, Asia/Shanghai. All new scripts, records and dumps are in this directory. Existing MATLAB desktop PID 264144, backend PID 380160 and MCP connection were retained. No intentional edits were made to the original preferences, Home database, or MATLAB installation. This is a diagnostic report, not a verified repair.

## Direct results

- Existing findings from the earlier `../startup-diagnostic/DIAGNOSIS.md` are imported evidence, not rerun: MATLAB R2026a build 26.1.0.3203278; 19 bounded cases; the empty startup plus pause(15) crashes; `satk_initialize` is not established as the root cause.
- [01: artifacts environment probe](01-artifacts-off/receipt.json): parent process had no `MW_ARTIFACTS_WS_ENABLED`; setting it to `0` only in the child, with isolated preference/temp directories and startup, ended after 5.513 s with exit `0xC0000005` after entering but before completing pause(30). The native stack again contains `mwhomesessionmanager_impl.dll+00268967` and `mwrecent_artifacts_service_impl.dll`. The variable appears in the installed binary, but no public MathWorks documentation or effective semantics were found. Thus this exact setting did not fix the crash; it is not proof that the service was disabled.
- [03: official Python Engine desktop startup](03-engine-desktop/receipt.json): Python 3.12.10 imported the preinstalled R2026a Engine and called `start_matlab('-desktop')` with isolated preferences/temp. Startup raised `EngineError: Transport stopped` before returning a session (5.015 s worker duration). The [crash dump](03-engine-desktop/temp/matlab_crash_dump.253152-1) has the same native location and recent-artifact caller. It did not reach the wait, simulation, or natural-quit checks. The worker exit code is not the MATLAB backend exit code.
- [05: GUI startup followed by named Engine connection](05-gui-share/receipt.json): directly started `bin/win64/MATLAB.exe -desktop -sd <isolated working dir>` with startup containing only a unique `matlab.engine.shareEngine` call, using isolated preferences/temp and APPDATA. GUI PID 35736 exited 1 before the unique name was discoverable (6.531 s total); the backend [crash dump](05-gui-share/temp/matlab_crash_dump.338660-1) shows the same fault location/caller. No session was attached, and the wait, simulation and quit were not reached. Isolated APPDATA remained empty, so this does not prove the Home database was redirected or test the same GUI path with the default APPDATA.
- The original MCP discovery file's SHA-256 before and after case 05 matched. At the end of the probes, process enumeration showed the original desktop/backend PIDs still alive and no newly retained MATLAB process. These checks do not assert anything about later activity.

Each probe used an isolated working directory, temporary folder and `MATLAB_PREFDIR`. The Engine and GUI workers used a Windows Job for bounded cleanup; only that new job's process tree was eligible for cleanup. No successful case qualified for a repeat. No long simulation was run. There is **no verified pause(30) + 0.02 s Simulink + natural zero exit** and no supported cold launcher produced.

## Home database and safety observations

Actual Home database: `C:\Users\Admin\AppData\Roaming\MathWorks\mwhome\mwhomeartifacts_1.db`. The ordinary settings folder is the separate sibling tree `...\MathWorks\MATLAB\R2026a`. Isolating `MATLAB_PREFDIR` does not by itself establish isolation of the Home DB. Previous case 05 overrode APPDATA in a batch process but did not trace actual file opens.

- One file (53,248 bytes) was observed in mwhome; no WAL, shared-memory or rollback-journal sidecar was present at that moment. SQLite read-only `integrity_check` and `quick_check` returned `ok`; journal mode was DELETE.
- [Read-only aggregate metadata](db-readonly-metadata.json): 91 rows, including 65 file, 25 folder and 1 project artifact; no NULLs in checked fields; no duplicate `(profileId,key)` pairs; all value fields were valid empty JSON objects. Raw recent paths were not printed or exported.
- [Point-in-time handle audit](home-handle-audit.json): 472 disk handles of the named MATLAB/MathWorks processes were inspected using duplicated handles and file IDs; only the audit process itself matched the DB. A temporary Win32 DELETE-access open on the DB and directory succeeded and was immediately closed; no rename occurred. Handles can change immediately; unrelated or inaccessible processes, service in-memory state and concurrent opens are not excluded. Two point-in-time DB hashes around case 01 and a later post-case-05 hash matched, but cannot establish absence of intermediate reads/writes.

- Final home-path check: the current process's USERPROFILE and concatenated HOMEDRIVE + HOMEPATH compare equal after Windows path normalization. Both directories opened, and Win32 final-path and volume/file identifiers matched. See [home-path identity](home-path-identity.json). Per the agreed condition no HOMEPATH startup probe was run.
- Authenticodes for both launch executables and the two fault-chain DLLs reported Valid. `VersionInfo.xml` reports 26.1.0.3203278, matching the earlier running-session report. Different component timestamps/version metadata are insufficient evidence of a mixed installation. Original DLL binaries were read only.

## Prospective reversible experiment; NOT performed

A running process may cache state, reopen files, or recreate mwhome immediately. A successful DELETE-access check does not prove a rename is safe while MATLAB or Service Host is active. Renaming it with the current Desktop/MCP active could split old and new state; restoring an old folder could hide history written during the experiment. MathWorks' published reset procedure is for the per-release settings folder and says to close MATLAB; no official mwhome-reset procedure was found.

A controlled experiment would require a separately authorized quiescent window for every writer and a decision about the live session, neither of which is available under the present no-stop constraint:

1. Inventory mwhome and verify SQLite journal mode and sidecars. Use SQLite's online backup API from a read-only connection to capture a transactionally consistent copy into this candidate directory, hash the backup, and run integrity checks **on the copy**. A raw copy of a live DB alone is not a sufficient backup. Preserve any sidecars and the original state.
2. Once all relevant writers are verifiably idle and the user permits the operation, rename the original directory to a unique sibling backup path on the same volume; retain it. Only then let the isolated cold process create a replacement and record precisely which path it opens. Run the defined pause(30), 0.02 s minimal test model and natural-exit checks twice if the first succeeds.
3. Stop only the experiment's own fresh process. With writers again verifiably idle, move the newly created directory to a unique quarantine name, restore the original sibling directory name, and compare the restored DB with the captured evidence. Keep both the snapshot and quarantine: writes generated during the experiment are not automatically merged, and any reconciliation needs a supported procedure. Do not overwrite or delete either copy.

Because the live Desktop/MCP cannot be stopped and application-level state has not been quiesced, this is a plan with unresolved safety conditions, not an assertion that it can currently be executed safely.

## Official references

- [MATLAB Engine start, desktop and quit](https://www.mathworks.com/help/matlab/matlab_external/start-the-matlab-engine-for-python.html)
- [Connect Python to a running shared session](https://www.mathworks.com/help/matlab/matlab_external/connect-python-to-running-matlab-session.html)
- [MATLAB MCP Server modes](https://github.com/matlab/matlab-mcp-server)
- [MathWorks clarification that MCP existing mode does not use Engine discovery](https://github.com/matlab/matlab-mcp-server/issues/66)
- [Where MATLAB stores per-release settings](https://www.mathworks.com/help/matlab/matlab_env/where-matlab-stores-settings.html)
- [MathWorks startup troubleshooting and reset](https://www.mathworks.com/matlabcentral/answers/97167-why-will-matlab-not-start-up-properly-on-my-windows-based-system)

## Reporting exception

The project-hub bound revision command was run once for the actual worktree `E:\Tesla_speed\worktrees\hellcat-state-contract-20261027`; it failed with `worktree does not belong to the registered repository`. No report was sent and no automatic retry was attempted. The parent task was notified.
