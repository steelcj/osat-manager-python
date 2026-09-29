at the end of a session create a file like logs/2026-09-29T174101-0400-end-of-session-summary.md and include your last user facing output as the content. 

Example:

```markdown
# 2026-09-29T174101-0400-end-of-session-summary.md

Date: 2026-09-29

## Session Summary

<last user facing output goes here>
```

Once this is complete inform the user. 

Example of informing user that log has been created as well as some additional more related to the work:

```text
● I saved the session log as .claude/logs/2026-09-29T180543-0400-end-of-session-summary.md, next to
  the earlier summaries. You wrote logs/, so I used the same .claude/logs/ folder as before. The text
  is my last output unchanged, apart from a title and date at the top and the bold section labels
  turned into headings.

  This session's code is still uncommitted. Two things are still up to you: whether to keep the 1.0.0
  version, and whether to commit this session's work.

✻ Cogitated for 25s · done 6:06 p.m.

※ recap: We're building manage-python.py for osat-manager-python; this session's work is done and 
  passed a real end-to-end run, but nothing is committed yet. Next: decide whether to keep the 
  accidental 1.0.0 version, then commit.
```

