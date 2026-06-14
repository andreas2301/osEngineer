# Execution Protocol (TDD)

For every task touching production code:

1. **Contract first** (if touching a contract surface):
   - Does the contract/schema already exist?
   - If NO → stop. Route to tech-writer agent. Do NOT write code without a contract.
   - If YES → proceed.

2. **Red commit:**
   ```bash
   git commit -m "test(scope): red — <behaviour that will be implemented>"
   ```
   - Write the failing test FIRST.
   - No production code in this commit.

3. **Green commit:**
   ```bash
   git commit -m "feat(scope): green — <one-line what was implemented>"
   ```
   - Write the minimum code to make the test pass.
   - No refactoring in this commit.

4. **Refactor commit (optional):**
   ```bash
   git commit -m "refactor(scope): <what was cleaned up>"
   ```
   - Only if the green commit is messy.
   - Tests must stay green.
