# RingLab — Lock-Free Circular Buffer

C++20 single-producer/single-consumer (SPSC) queue and interactive browser lab by Yubraj Chaulagain. A newly built portfolio implementation of the circular-buffer project described in the supplied resume. No client code or data.

## What works

- Native bounded FIFO with `std::atomic`, acquire/release publication, 64-byte-aligned head/tail counters and nonblocking push/pop attempts.
- Capacity checks, FIFO ordering, wraparound and actual two-thread correctness tests.
- A native benchmark comparing the queue with a bounded mutex-protected ring under the same capacity and message count. Results are exported as JSON.
- Deployed browser lab: adjustable capacity and producer/consumer attempt rates, pause/reset, manual push/pop, full/empty feedback, FIFO contents and downloadable operation trace.
- Recorded native benchmark display and import of locally generated benchmark JSON.

## Native build and test

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/ringlab > benchmark.json
```

Requires a C++20 compiler and lock-free `std::atomic<std::size_t>`; unsupported targets fail the compile-time assertion. GCC 13.3 was used for the included results. The test executable also works directly with `g++ -std=c++20 -O3 -pthread main.cpp -o ringlab` followed by `./ringlab --test`.

## Browser lab

```sh
npm test
npm start
```

Requires Node 20+ for model tests and Python 3 for the static server. Open http://localhost:8000. Static assets live in `dist` and require no build or external dependencies.

## Correctness boundary

Exactly one producer may call `push` and exactly one consumer may call `pop`. Construction/destruction must be externally synchronized. Do not copy, move, reset or destroy a queue while threads use it. Payloads are unsigned 64-bit integers. The native ring reserves one physical slot to distinguish full and empty; usable capacity is the template argument. The browser model uses an explicit count and displays only usable slots, so its pointer indexes illustrate FIFO behavior rather than reproducing the native sentinel index.

The producer writes a slot before publishing head with release ordering; the consumer observes head with acquire ordering before reading. Tail uses the corresponding release/acquire handoff before slot reuse. The operation attempts contain no locks or retry loops; the benchmark harness retries and yields when full/empty. 64-byte counter alignment is a layout choice, not a measured 30% contention improvement.

The browser animation is a sequential JavaScript model, **not execution of the native concurrent queue**. It is not a throughput benchmark. Timers are approximate and may be throttled in background tabs. The trace retains the last 200 operations; the screen shows the latest 30. Changing capacity resets the experiment.

## Measurements and verification

`dist/benchmark.json` contains a real execution from the build container: five rounds of one million messages, capacity 1,024, median messages/second, alternating execution order. Threads were unpinned in a shared container. Scheduling, CPU state, compiler and contention affect these numbers; no universal ratio is claimed. No perf/valgrind or thread sanitizer results are claimed. The resume's original 3.2× and 30% claims were not independently reproduced.

Passed: native empty/full/FIFO/wraparound/capacity-one checks, one million concurrent transfers, two JavaScript model tests including 10,000 reference-queue operations, and JavaScript syntax validation. Browser interaction/visual QA was not performed.

This demo is independent of Woodcrest/CrestMind and OM Produce, which were excluded from implementation.
