import os

# Intent: processes these tests start are started by whoever runs them; when that is an AI assistant (Stowers
# Institute's policy for AI-started processes), they must carry its name, so the suite runs with the Claude prefix. Set
# EVERYOME_JOB_PREFIX yourself to test with another (test_slurm checks the empty default separately).
os.environ.setdefault("EVERYOME_JOB_PREFIX", "Claude")

# Intent: the fixture community module carries its own tests; they run in the registry's CI, not here.
collect_ignore_glob = ["fixtures/*"]
