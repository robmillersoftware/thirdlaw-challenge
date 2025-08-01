**TIMELINE**

***10:00 - 10:30 - Create prototype and solve initial challenge***

Created initial prototype using Claude Code

***10:30 - 10:50 - Meeting with Luke***

Discussed the current state of the prototype, clarified some open questions. Decided to make the rest of the time focus on performance and scalability.

***10:50 - 11:20 - Polish and get bonus points***

Added redaction functionality and metrics collection.

***11:20 - 11:50 - Set up deployment and test environment*** 

Generated test data and set up load testing. Used testing data to determine next steps.

Was able to reach 14.8 req/sec with the fully synchronous processing. The timing for the workflow looks like this:

```
File I/O: ~50ms 
PDF text extraction: ~150ms
Regex processing: ~50ms
Database write: ~20ms

Total: ~270ms, but only ~70ms benefits from threading
```

***11:50 - 12:15 - Optimizations***

* Force garbage collection to improve memory usage
* Added thread pool and offloaded upload endpoint to async

Was able to reach 19.7 req/sec with these optimizations. The bottleneck is still 

***12:15 - 12:45 - Further optimizations***

* Switched to ProcessPoolExecutor instead of ThreadPoolExecutor. Now we can have multiple I/O bound workers running on each CPU core
* Switched to Prometheus + Grafana for metrics instead of rolling our own

***12:45 - 13:45 - Metrics Dashboard***

Decided to timebox an hour to spend on a metrics dashboard to help with the POC as well as to add a new feature
