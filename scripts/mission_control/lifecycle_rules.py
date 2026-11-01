"""The allowed step statuses, stop reasons and step-status changes, in one place."""

STEP_STATUSES = ('pending', 'in_progress', 'completed', 'blocked', 'awaiting_approval')
STOP_REASONS = ('done_verified', 'blocked', 'human_paused', 'human_abort', 'no_progress', 'budget_exhausted', 'max_iterations')
# Reasons the stop command may record; done_verified only comes from finish.
OPERATOR_STOP_REASONS = STOP_REASONS[1:]

# Status changes one command may make; a step with no entry yet counts as pending.
STATUS_TRANSITIONS = {
    'pending': {'in_progress', 'awaiting_approval', 'blocked'},
    'in_progress': {'pending', 'completed', 'blocked'},
    'awaiting_approval': {'pending', 'blocked', 'in_progress'},
    'blocked': {'pending', 'awaiting_approval', 'in_progress'},
    'completed': {'pending'},
}
