# Optional measurement

The skill works without hooks. Add these if you want to compare predictions with observed elapsed time and tool-call counts. Requires Python 3.

## Connect the hooks

After [installing the skill](../README.md#install), merge the following entries into `~/.claude/settings.json`. Preserve existing settings and append to any existing arrays for these events.

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/skills/dog-years/dog.py event"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 ~/.claude/skills/dog-years/dog.py event"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/skills/dog-years/dog.py event"}]}]
  }
}
```

Start a new session after changing hook settings.

## Record a task

Run these from the project directory where the agent is working:

```sh
# Before starting: predicted tool calls, then predicted minutes.
python3 ~/.claude/skills/dog-years/dog.py predict unique-task-name 20-40 10-25

# After checking that the task is complete:
python3 ~/.claude/skills/dog-years/dog.py resolve unique-task-name

# Inspect the measurements:
python3 ~/.claude/skills/dog-years/dog.py report

# Write the report into the installed skill's calibration section:
python3 ~/.claude/skills/dog-years/dog.py table
```

The skill instructs Claude to use this sequence for work it has estimated. The hooks collect events; they do not create a prediction on their own.

## Data and limits

Data stays in `~/.claude/dog-years/`, unless you set `DOG_YEARS_DATA`. The helper records timestamps, event types, working directories, session identifiers, tool names and task predictions. It does not record prompt text or tool arguments.

Elapsed time includes human interruptions and service waits. Tool counts are grouped by working directory and time window, so concurrent sessions in the same directory can mix counts. Prediction resolution matches task names, so use unique names across projects. A missing explicit resolution can fall back to a Stop event; the report marks these inferred endpoints with an asterisk. A Stop event does not prove task completion.

Treat the current report as experimental instrumentation. The [calibration evaluation](../skill/EVAL.md) describes how to test whether feeding measurements back improves future predictions.
