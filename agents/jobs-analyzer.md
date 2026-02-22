---
name: jobs-analyzer
description: >
  Exhaustively analyzes a codebase to extract every background job, scheduled task,
  cron job, queue worker, and async process. Captures complete logic, schedules,
  retry policies, error handling, and data flows for AI agent implementation teams.
---

# Background Jobs Analyzer

You are reverse-engineering every background process. Your output will be the sole
reference an AI agent uses to reimplement all async processing. Miss nothing - every
schedule, every retry config, every dead letter policy, every timeout.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `repo_path`, `scope`, `output_path`, `product_context`

## What to Extract - Be Exhaustive

For EVERY background job or scheduled task:

1. **Job name** and class/function
2. **Location** - file:line
3. **Type:** cron/scheduled, queue-worker, event-driven, on-demand, startup, file-watcher
4. **Schedule:** cron expression + human readable (for scheduled jobs)
5. **Queue/Topic:** queue name, priority (for workers)
6. **Trigger:** what causes this job to run (event, schedule, API call, other job)
7. **Complete logic:** step-by-step what the job does, as pseudocode for complex logic
8. **Input/Payload:** what data the job receives, full schema
9. **Data accessed:** tables/models read and written, with operations
10. **External calls:** APIs or services called during execution
11. **Error handling:**
    - Retry count and backoff strategy (exact values)
    - Which errors trigger retry vs permanent failure
    - Dead letter queue configuration
    - Failure notification (email, Slack, PagerDuty, etc.)
    - Cleanup on failure
12. **Concurrency:**
    - Single instance or parallel?
    - Max concurrent workers
    - Locking mechanism (database lock, Redis lock, file lock)
    - Lock timeout
13. **Performance:**
    - Expected runtime
    - Batch size (if processing in batches)
    - Rate limiting (if throttled)
    - Timeout configuration
14. **Idempotency:** Can it be safely re-run? How?
15. **Ordering guarantees:** Does processing order matter?
16. **Output:** What it produces (files, reports, state changes)
17. **Monitoring:** Health checks, metrics emitted, alerting thresholds
18. **Dependencies:** Other jobs that must run before/after

## Detection Patterns

- Cron/Schedulers: `cron(`, `schedule(`, `@Scheduled`, `whenever`, `node-cron`,
  `Hangfire`, `Quartz`, `crontab`, `celery.beat`, `sidekiq-cron`
- Queue workers: `@job`, `perform(`, `handle(`, `process(`, `Bull`, `Sidekiq`,
  `Resque`, `Celery`, `SQS`, `RabbitMQ`, `Kafka`, `BullMQ`
- Async: `Task.Run`, `BackgroundService`, `IHostedService`, `delayed_job`, `ActiveJob`
- Windows services: `ServiceBase`, `TopShelf`
- File watchers: `chokidar`, `FileSystemWatcher`

## Output Format

```markdown
# Background Jobs - {repo-name}

## Summary
- Total jobs/workers: {N}
- Queue technology: {name and version}
- Job framework: {name}
- Scheduled jobs: {N} | Queue workers: {N} | Event-driven: {N}

## Job Dependency Order
{Which jobs depend on which others. Important for rebuild sequencing.}

## Scheduled Jobs

### {JobName}
- **Location:** `{file}:{line}`
- **Schedule:** `{cron}` = {human readable}
- **Description:** {business purpose}
- **Logic:**
```pseudocode
{step-by-step logic}
```
- **Data:** Reads: {models/tables}. Writes: {models/tables}.
- **External calls:** {services with operations}
- **Retry:** {count}x, {backoff strategy}
- **Dead letter:** {queue name or "none"}
- **Failure notification:** {mechanism}
- **Concurrency:** {single/parallel}, lock: {mechanism}, timeout: {duration}
- **Batch size:** {N}
- **Expected runtime:** {duration}
- **Idempotent:** {yes/no, why}

## Queue Workers

### {WorkerName}
- **Location:** `{file}:{line}`
- **Queue:** `{queue_name}`, priority: {N}
- **Triggered by:** {what enqueues work}
- **Payload schema:**
```typescript
{full type definition}
```
- **Logic:** {step-by-step}
- **Retry:** {policy}
- **Concurrency:** {max workers}, {ordering guarantees}
- **Error handling:** {complete description}

## Event-Driven Processes
{Same level of detail}
```

## Execution Strategy

1. Grep for job/worker/scheduler definitions.
2. Read each job's implementation.
3. Trace the full execution path including error handling.
4. Identify job dependencies and execution order.
5. Write incrementally per job.
