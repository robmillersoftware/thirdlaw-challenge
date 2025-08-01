**TIMELINE**

***10:00 - 10:30 - Create prototype and solve initial challenge***

Created initial prototype using Claude Code

***10:30 - 10:50 - Meeting with Luke***

Discussed the current state of the prototype, clarified some open questions. Decided to make the rest of the time focus on performance and scalability.

***10:50 - 11:20 - Polish and get bonus points***

Added redaction functionality and custom metrics collection. Claude decided we should roll our own metrics collection for some reason. I imagine we're going to switch to Prometheus or something soon.

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

Was able to reach 19.7 req/sec with these optimizations. Something tells me I'm doing threads wrong.

***12:15 - 12:45 - Further optimizations***

* Fixed the thread pool issue. Previously, we were running a single FastAPI instance, which meant our threads were fighting for a single CPU core thanks to Python's Global Interpreter Lock. The fix was to run with multiple FastAPI worker processes.
* Switched to Prometheus + Grafana for metrics instead of rolling our own

***12:45 - 13:30 - Metrics Dashboard***

Decided to timebox an hour to spend on a metrics dashboard to help with the POC as well as to add a new feature

Got it mostly working, but sadly it doesn't accurately show the most important throughput data point: req/sec. I'll try to figure out how to fix it as I go.

***13:30 - 14:00 - Hardening***

I've got a LOT of code and configuration that I haven't actually seen yet. Time to do some reading and editing.

***14:00 - 15:00 - Deployment***

* Put the app behind a load balancer with Docker Swarm and spun up 4 replicas of the service. We're up to 139.4 requests/second.
* Need to identify a cloud provider then deploy the app. I've already got everything containerized, so hopefully it won't be too painful.

