## Progress observation — <timestamp>

- **Classification**: progress | verified_wait | no_progress
- **Authoritative evidence**: changed artifact/check result, or owning system's live handle/status.
- **Meaning for the original goal**: requirement advanced or blocker identified.
- **If waiting**: exact handle/identity, last observation, bounded next poll; do not restart on a polling timeout.
- **Next authorized action**: specific action; no approval inference or counter reset.

Use in the decision log. Approval waiting remains the CLI's awaiting_approval
state; an old log, plan or lock file alone cannot establish a verified process wait.
