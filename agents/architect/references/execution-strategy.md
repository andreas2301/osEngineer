# Serial Feature Execution & Read-Only Parallelization

You must govern the execution strategy across the workbench based on these system invariants:

- **Serial Feature Execution:** All feature implementation, writing, and modification tasks (write operations) must be executed sequentially (one feature at a time). Never allow multiple developer agents to concurrently edit overlapping files or execute parallel feature branches. This maintains a clean Git topology, avoids structural code conflicts, and ensures a singular source of truth.
- **Read-Only Parallelization:** You may parallelize read-only operations (such as codebase discovery, grep searches, AST symbol lookups, and log checks). Instruct multiple research agents or tools to execute in parallel threads to maximize discovery speed while the main write stream remains strictly sequential.
