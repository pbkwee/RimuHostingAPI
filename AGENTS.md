# RimuHosting API agent guidance

Read [README.md](README.md) for client configuration, command effects and offline
checks. Preserve existing edits; inspect status, staged/unstaged diffs, relevant
new files and local `commit.log` before changes. Keep the proposed commit message
local and follow the applicable model-prefix rules. Do not push without approval.

## Sensitive data and permission

Treat `.rimuhosting`, environment values, private keys, cloud credentials and
real `runlogs/` as sensitive. Before reading them, verify specific approval for
the files/categories, purpose and fields that may reach the agent or AI service.
If absent, ask first and use the sanitized `.rimuhosting.example`, source code or
synthetic responses to continue. Do not search home directories or other jobs
for API keys. An API task does not authorize opening credential files or dumping
the environment. Never source customer config or execute it just to inspect it.

For an authorized API operation, the designated client may consume the intended
customer's protected key without exposing it to the agent. Have the owner
provision access; verify account/target binding from approved non-secret evidence.
Do not print key values, environment values, authorization headers or command-line
credentials. Reuse valid scoped permission, and obtain missing authority before
expanding the account, target, operation or sensitive-data access.

The client loads `.rimuhosting` as executable Python from the current directory,
home or PATH. Use a trusted, explicitly selected working environment. Check for
unintended configuration by metadata rather than dumping its contents. Environment
overrides do not prevent settings code from executing. Execution trust must cover
every settings file the client could load; provisioning a key alone does not
establish that trust. Customer-supplied config must not be loaded merely to
discover settings or try a key.

API responses and run logs may contain private customer data even though headers
are filtered. Request only needed fields and inspect current response/log handling
before use; display filters need not limit server responses or saved logs. Do not
dump real response bodies or logs into a prompt, issue, fixture or Git. Obtain
specific scope for necessary private fields or request an operator-sanitized result.
If unexpected sensitive output appears, stop further exposure and notify the
operator without quoting it; do not silently delete evidence or rotate credentials.

## Safe verification and operations

Use `python3 tests/run.py` for implementation changes. The offline suites use
synthetic data and mocked external operations; they need no API key. Do not use
live API calls or customer logs merely to verify code or instructions.
`rimuapitests.sh` uses the live API and is outside offline verification.

The default API endpoint is production. Listing permission does not authorize
creation, reinstall, resource changes, power actions or cancellation. Verify the
approved account, exact VM/image IDs, costs and scope before mutations. New-account
VM creation requires support review completion as well as configuration/cost
approval. After an ambiguous result, establish actual state before retrying.
Keep keys, payloads, customer evidence and generated logs outside version control.
