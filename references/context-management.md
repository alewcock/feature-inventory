# Context Window Management Guide

This reference is for all feature-inventory agents. Follow these rules to avoid
context exhaustion during analysis.

## Your Purpose

You are producing a specification that an AI/agent team will use to rebuild this
product from scratch. Your output is the ONLY reference they will have. This means:
- Completeness matters more than speed
- Every detail matters (defaults, edge cases, error messages, magic numbers)
- But you must manage context carefully to actually finish the job

## Hard Rules

1. **Never read a file without a line range** unless it's under 50 lines.
   Use `Read` with line ranges: `Read {file} lines 1-100`, then `lines 101-200`, etc.

2. **Never hold more than ~200 lines of source code in context at once.**
   Process a section, extract findings, write them to disk, then move on.

3. **Write incrementally.** After analyzing each module/file/component, append
   findings to the output file immediately. Don't accumulate everything in
   conversation context.

4. **Use Grep and Glob before Read.** Discovery should be:
   - `Glob` to find candidate files
   - `Grep` to find specific patterns and line numbers within files
   - `Read` (with line range) only for the specific lines you need to understand

5. **Process one logical unit at a time.** One endpoint, one model, one screen,
   one job. Extract it fully (every field, every edge case), write it, move on.

6. **Count your work.** After every ~20 items written, do a quick self-check:
   "Am I still operating efficiently, or has context grown too large?" If you feel
   like you're losing coherence, finalize what you have and note where you stopped.

## Incremental Write Pattern

```
First write (create file):
  Write the header/summary placeholder
  Write the first few findings

Subsequent writes (append):
  Read the last few lines of the output file to maintain continuity
  Append new findings

Final write:
  Go back and fill in the summary section with counts
```

## Exhaustiveness vs Context Limits

You might think "I can't capture everything because of context limits." Wrong approach.
The strategy is:
1. Capture one thing COMPLETELY (every field, every default, every edge case)
2. Write it to disk
3. Move to the next thing
4. Repeat

You don't need to hold the whole inventory in context. You just need to hold one
item at a time and write it out.

## When a Dimension Has Many Items

If a single dimension has 100+ items:
1. **Do not reduce depth.** Every item still gets full detail.
2. **Group items into logical sections** as you go.
3. **Write each section as you complete it.**
4. **If you must stop mid-dimension**, write a `## INCOMPLETE - Stopped at {location}`
   marker so the next run knows where to resume.

## Flagging Ambiguity

When you encounter something unclear:
- Complex conditionals with no comments
- Dead code that might or might not be active
- Config values that could mean multiple things
- Half-implemented features
- Behavior that seems like a bug vs intentional

Tag it inline: `[AMBIGUOUS] {description of what's unclear}`

The orchestrator will collect these and ask the user.

## Failure Recovery

If you're spawned and the output file already has partial content:
1. Read the last 30 lines to see where previous analysis stopped.
2. Look for `## INCOMPLETE` markers.
3. Continue from where it left off.
4. Don't duplicate entries that already exist in the file.
