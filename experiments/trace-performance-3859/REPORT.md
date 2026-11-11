# PR #3859 performance investigation

## Conclusion

Keep the current OnceLock design for review, provisionally. The mixed-workload advantage reproduces on this machine and the controlled alignment experiment implicates allocation layout. It does not establish the exact cache-line mechanism or prove this design best on other machines. The claimed SimpleSpanProcessor regression was not reproduced in the longer repeat; significant variability remains. No production changes are justified by these results alone. Remaining work includes independent profiling, allocation counts, and cold/warm cost decomposition.

## Sources and reproducibility

- A: `1e29b1fe1d03bde8e48eb564a3dee8ec9efed6a7` (PR base, already includes #3774)
- B: `28e4bc4d13a642c3f889105399db1dc241e3d9ab` (PR head)
- C: `02826b01125941891aed8de2f3b6b8c987de2495` (eager experiment, direct child of B)
- D: diagnostic C plus only `#[repr(align(64))]` on `SdkTracerInner`; see `alignment.patch`. D changes allocation size and alignment, and is not a production recommendation.

Between B and C, only `tracer.rs` and one test name in `span.rs` differ. Between A and B, besides ownership changes, the PR adds tests, the scaling benchmark, its manifest entry, and changelog text. A does not contain the benchmark, so the previous A harness identity and previously used lockfile cannot be independently established from the commits. This investigation injects the exact same `harness.rs` and benchmark declaration into all three archive snapshots. The lockfile here was generated offline once and copied to all snapshots (SHA-256 `7e92c858276e4bc4ca4b8e2f4bee49929b3e1c5542b237424350e6d085ed26a7`). It may differ from the earlier experiment's dependency resolution.

Host: AMD Ryzen 5 5600H, 6 cores / 12 threads, Linux Fedora `6.19.10-300.fc44.x86_64`, rustc 1.99.1 (58cf8f9c3, LLVM 23.1.1), 64-byte L1 data cache line, performance governor. CPU affinity was not pinned and background load was present. No temperature or frequency time series was collected. No explicit `RUSTFLAGS`, target-cpu override, or OTEL environment variables were set. `cargo bench` used the workspace bench profile (optimized, line-table debug info), default features and one shared lockfile. The setup is not a controlled bare-metal laboratory.

The original harness starts timing after barrier release and stops after joining, so it excludes a little worker activity and includes shutdown/join time. This diagnostic starts timing immediately before barrier release and stops immediately after setting the stop flag, still counts in-flight completions after the flag, and retains the coordinated barrier. Its timing is therefore an approximation too. Every operation starts a root span with a fixed start time, ends at a fixed time, then passes the resulting span through `black_box` before dropping it. The original does not call `black_box`; results are not directly interchangeable. Random IDs and sampling are kept, and the result is consumed to guard against optimizer elimination. SimpleSpanProcessor uses the original void exporter, which returns a ready future without I/O. The no-op processor implements both callbacks and shutdown as no-ops; merely registering it causes SDK span-data conversion and callback dispatch.

Each configuration received a 150 ms warm-up process and nine sequential 300 ms measurement processes, with A/B/C rotated and configuration order fixed. Each process constructs one provider and shares one tracer across workers. `raw.csv` includes every run, order, counts, duration, and throughput. The separate sampling check counts `is_recording()` in worker-local variables; this check is not part of the timed throughput measurements. The ratios in all 18 checks were 49.932% to 50.025% recording. `summary.csv` reports medians, minima, maxima, and median absolute deviations (MAD) in millions of spans per second. Raw rounds are independent processes but share machine conditions; no confidence intervals were calculated.

To reproduce in a fresh copy of this artifact directory, set `OTEL_REPO` to a clone containing the three commits, run `python3 build.py`, then `OTEL_BENCH_BIN_DIR=/tmp/otel-perf-reproduce python3 run.py`, `python3 summary.py`, `OTEL_BENCH_BIN_DIR=/tmp/otel-perf-reproduce python3 layout.py`, and `OTEL_BENCH_BIN_DIR=/tmp/otel-perf-reproduce python3 processor.py`. The build script refuses to overwrite `/tmp/otel-perf-reproduce`; runners refuse to overwrite existing CSV files, so copy this directory to a new location and remove the copied output CSVs only when deliberately starting a new run. Builds require the locked dependencies in the local Cargo cache because they use `--offline`. `build.py` uses a separate target directory per revision; the original run used a shared target directory but forced SDK rebuilds and copied each binary before building the next.

## Main results

M spans/s; values are median ± MAD, nine 300 ms measurements. Percentage is B relative to A.

| Workload | Workers | A | B | C | B vs A |
|---|---:|---:|---:|---:|---:|
| Mixed | 1 | 10.969 ± 0.165 | 10.747 ± 0.160 | 11.214 ± 0.188 | -2.0% |
| Mixed | 2 | 12.320 ± 0.419 | 14.088 ± 0.270 | 11.773 ± 0.242 | +14.4% |
| Mixed | 4 | 14.461 ± 0.217 | 18.985 ± 0.263 | 13.537 ± 0.101 | +31.3% |
| Mixed | 6 | 15.608 ± 0.056 | 22.278 ± 0.213 | 14.488 ± 0.100 | +42.7% |
| Mixed | 8 | 17.314 ± 0.075 | 24.292 ± 0.428 | 16.193 ± 0.091 | +40.3% |
| Mixed | 12 | 19.286 ± 0.324 | 26.705 ± 0.659 | 18.222 ± 0.266 | +38.5% |
| Recording, no processor | 1 | 9.762 ± 0.140 | 9.955 ± 0.115 | 10.139 ± 0.120 | +2.0% |
| Recording, no processor | 4 | 13.230 ± 0.224 | 15.105 ± 0.065 | 12.142 ± 0.083 | +14.2% |
| Recording, no processor | 8 | 16.762 ± 0.225 | 17.260 ± 0.120 | 13.083 ± 0.073 | +3.0% |
| Recording, no-op processor | 1 | 7.526 ± 0.063 | 7.736 ± 0.099 | 7.705 ± 0.180 | +2.8% |
| Recording, no-op processor | 4 | 17.855 ± 0.230 | 19.099 ± 0.127 | 12.291 ± 0.328 | +7.0% |
| Recording, no-op processor | 8 | 21.404 ± 0.793 | 24.082 ± 0.295 | 12.786 ± 0.130 | +12.5% |
| AlwaysOff | 1 | 13.143 ± 0.171 | 11.732 ± 0.091 | 13.198 ± 0.108 | -10.7% |
| Simple + void | 4 | 8.317 ± 0.309 | 8.084 ± 0.113 | 10.975 ± 0.085 | -2.8% |
| Simple + void | 8 | 5.648 ± 0.081 | 5.724 ± 0.081 | 5.863 ± 0.060 | +1.3% |

Minima and maxima, including important outliers, are in `summary.csv`. In particular, 4-worker Simple A ranges 6.492 to 11.324M/s and C ranges 7.064 to 11.249M/s: the table's apparently large median differences do not establish a reliable ordering. Eight-worker mixed B exceeds C by 50.0% in median throughput; the individual ranges do not overlap in this run.

## Layout experiment

In an additional rotated nine-round, 300 ms experiment, B/C/D medians at eight workers were 24.35/15.91/23.04 M/s for mixed, 17.10/12.87/24.79 for recording without a processor, and 23.02/12.29/23.08 for the no-op processor. `layout.csv` contains all results and ranges. D's only source change is the explicit 64-byte alignment on the inner type. This is strong evidence that the original layout affects these synthetic results on this host, but alignment also changes allocation placement and footprint. No hardware cache-line profile or allocation-address tracing was available, so neither false sharing nor a specific location is proven. This experiment does not justify adding alignment to the PR.

The Arc strong and weak counts live in their respective heap allocations, not in the Arc pointer field. Recording spans in A increment both the separate scope and provider counts; B/C increment the inner allocation count. Non-recording spans increment a detached scope allocation's count. C reads the stored scope pointer from the shared inner allocation, whereas B uses its lazy field; both paths also read provider state. Recording spans without processors do not need to access scope metadata during end. With processors, export-data construction accesses the recording span's scope. Sharing of a cache line between reference counts and frequently read inner fields is a plausible explanation, but compiler-generated accesses, allocator placement, and cache-coherence traffic were not directly observed. Sampling, extra dereferences, and layout remain possible contributors. `perf`, `heaptrack`, and `valgrind` were not available on PATH; `perf_event_paranoid` was 2, but no perf access test was possible.

## Processor investigation

The path is build_with_context -> sampling -> recording span construction -> processor on_start -> end_with_timestamp -> end_and_export -> span-data construction -> on_end. SimpleSpanProcessor takes ownership of the finished data, checks shutdown, locks the shared exporter mutex, allocates a one-element Vec, and synchronously runs the void export future under the lock. Baseline and PR use the same processor/exporter logic; the ownership and access path changes. The mutex can dominate under contention, but this does not establish that the PR has no effect.

A second warm-up plus nine one-second rotated processes for Simple + void produced:

| Workers | A median (min–max; MAD) | B median (min–max; MAD) | C median (min–max; MAD) | B vs A |
|---:|---:|---:|---:|---:|
| 4 | 6.824 (6.590–7.774; 0.234) | 7.508 (6.530–7.688; 0.181) | 8.655 (7.883–9.734; 0.768) | +10.0% |
| 8 | 5.135 (4.991–5.237; 0.069) | 5.306 (5.142–5.443; 0.082) | 5.395 (5.189–5.526; 0.130) | +3.3% |

`processor.csv` has the individual runs. The earlier 25% four-worker regression was not reproduced; overlapping ranges preclude a precise general claim. In the short no-op runs B also did not regress against A, but that processor still runs both callbacks and data construction; it does not isolate callback registration from execution. A representative batching/export configuration, lock hold times and hardware profiles were not measured. The results do not show whether a smaller regression exists under another workload.

## Non-recording and tracer costs

At one worker, AlwaysOff B is 10.7% lower throughput than A, while C is near A. Reciprocal medians are about 85.2, 76.1 and 75.8 ns per operation respectively, but this is the reciprocal of throughput for this full harness, not a measured isolated OnceLock lookup. Sampling, construction, end, drop, black_box and loop overhead are included. Cold initialization, warm get_or_init, Arc clone, sampling, and span construction/drop were not separately timed; attributing the entire difference to the OnceLock check would be unsupported.

Source inspection shows A allocates a scope Arc in tracer construction; B allocates one inner Arc and allocates a detached scope Arc only on first non-recording span; C allocates both inner and scope Arcs eagerly. Relative counts describe these ownership allocations only, not total tracer/provider construction. Cloning a scope for B's first non-recording span may also allocate for its metadata. Allocation counts, tracer-creation latency and representative attribute costs were not measured in this run. Cached-tracer applications amortize creation, but frequently reconstructed tracers pay it repeatedly. Do not reuse earlier numerical allocation or latency claims as newly verified results.

## Correctness and review

`cargo test --locked --offline -p opentelemetry_sdk --all-features --lib` in the B archive: 518 passed, 0 failed, 25 ignored. `cargo clippy --locked --offline -p opentelemetry_sdk --all-targets --all-features -- -Dwarnings` in the B archive with the original PR harness: passed. `cargo fmt --all -- --check` in the checkout: passed. `git diff --check 1e29b1fe 28e4bc4d`: passed. No source changes were made in the checkout. The library tests include recording provider retention after end, attached-context lifetime, mixed recording/non-recording lifetime, cross-thread transfer, concurrent lazy initialization, and scope metadata. The 25 ignored tests were not run, and no new end-to-end integration or platform tests were performed.

Source review found no demonstrated correctness blocker. Non-recording scope is detached from the provider; recording spans hold the tracer through end until drop, preserving the relevant lifecycle. The added mixed-lifecycle test overlaps some existing tests but also combines independent claims, so a reduction should preserve that combined lifetime case, concurrent initialization and metadata checks. The exact two-word `SpanOwner` layout assertion depends on Rust enum layout and should be assessed as a portability/performance-test tradeoff rather than a correctness guarantee. There is no evidence to remove the inline annotations as a performance fix without another controlled build.

The benchmark should be interpreted cautiously: its timer includes joins and its default table omits raw rounds and cross-implementation rotation; `repeats=0` also panics. A change to the production harness should be proposed separately only if the maintainers want it. The changelog's contention reduction is plausible but the exact measured gain depends on workload and host. Update the PR text that still says #3774 must merge first. Do not cite an unmeasured cache-line mechanism as fact.

## Reviewer preparation brief

No implementation changes or divergence from the PR were made. The alignment variant is diagnostic and deferred. Automated checks are listed above; no separate manual end-to-end test or profiler run was performed. Useful self-review anchors: `opentelemetry-sdk/src/trace/tracer.rs` at `non_recording_scope` for the lazy allocation and provider-lifetime tradeoff; `opentelemetry-sdk/src/trace/span.rs` at `SpanOwner` for retaining the provider through drop; and `opentelemetry-sdk/benches/trace_scaling.rs` at `measure_op` for the timing limitations. The contributor should verify these claims and choose their own PR narrative.

## Draft PR description

Related to #3838. #3774 has merged and is included in the base.

Recording spans currently clone separate scope and provider Arcs. This change keeps them together in one tracer inner Arc so recording spans update one reference count. Non-recording spans keep a detached scope Arc, initialized on first use, so they do not keep the provider alive. Recording spans continue to retain the provider until they are dropped, including after `end()`.

On one Ryzen 5 5600H, using a separate rotated diagnostic harness with nine 300 ms runs, median mixed throughput at eight workers was 17.31M spans/s on the base and 24.29M/s with this change. Single-worker AlwaysOff throughput was 13.14M/s and 11.73M/s respectively. These are synthetic results and depend on layout and workload. A longer SimpleSpanProcessor + void exporter rerun did not reproduce the previously observed regression; individual results overlap.

Validation: SDK all-features library tests (518 passed, 25 ignored), SDK all-targets/all-features Clippy, and formatting check. The diagnostic harness and raw data are separate from this PR.

## Draft follow-up comment

I compared the lazy and eager versions with the same harness and rotated their order across runs. At eight workers the mixed workload still favored the lazy version on my machine, and a separate count showed the sampler was close to 50/50. Aligning the eager tracer inner allocation narrowed that gap, so layout seems to matter, though I can't tell which cache line is responsible without profiling.

The earlier SimpleSpanProcessor regression didn't reproduce in a longer rerun, but the results were noisy. The lazy version still costs some single-threaded non-recording throughput, so I think keeping it is a reasonable tradeoff for now. I'll avoid claiming that the alignment experiment proves a specific contention mechanism.
