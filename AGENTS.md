# RouteRescue AI — Agent Development Instructions

## 1. Autonomous Development

For every development task:

1. Analyze the requirements.
2. Inspect the existing codebase.
3. Identify dependencies and affected components.
4. Implement the requested functionality.
5. Execute the code.
6. Run relevant unit and integration tests.
7. Identify errors, exceptions, and failed tests.
8. Debug and correct the underlying issues.
9. Rerun the tests.
10. Repeat the debugging cycle until the tests pass or a genuine external blocker prevents further progress.

Do not stop immediately after encountering an error.

## 2. Mandatory Verification

After every development phase:

- Run the relevant automated tests.
- Verify that existing functionality still works.
- Check imports and dependencies.
- Verify API endpoints.
- Verify agent-to-agent communication where applicable.
- Check database operations.
- Validate input and output schemas.
- Check error handling.
- Perform an end-to-end test when the phase introduces a complete workflow.

Do not claim success based solely on code generation.

## 3. Autonomous Debugging

When an error occurs:

1. Read the complete error message and traceback.
2. Identify the root cause.
3. Apply the smallest reliable fix.
4. Rerun the failed test.
5. Check for regressions.
6. Document significant fixes.

Do not suppress errors, remove important tests, or replace failing functionality with hardcoded responses simply to make tests pass.

## 4. Fetch.ai Integration

Use current official Fetch.ai uAgents, Agentverse, and ASI:One documentation.

Do not invent SDK methods or unsupported integrations.

Verify agent communication through actual message exchanges.

Use mocks only in explicitly designated tests.

## 5. Security and Reliability

- Never expose API keys or private agent seeds.
- Use environment variables for credentials.
- Never claim simulated transport information is live.
- Never initiate bookings or payments without explicit user approval.
- Handle timeouts, unavailable services, and invalid inputs.
- Avoid destructive operations unless explicitly authorized.

## 6. Completion Requirements

A phase is complete only when:

1. The requested functionality has been implemented.
2. Relevant tests pass.
3. The implementation has been executed successfully where the environment permits.
4. No known critical errors remain.
5. Existing functionality has not regressed.

If external credentials, unavailable services, or environment restrictions prevent verification, clearly report the blocker rather than claiming completion.

## 7. Development Reports

After every phase, provide a concise report containing:

- Features implemented
- Files created or modified
- Tests executed
- Tests passed and failed
- Bugs discovered and fixed
- Remaining limitations
- Instructions for manual verification, if necessary

## 8. Continuous Development

Maintain compatibility with previously completed phases.

Do not unnecessarily rewrite working components.

Prefer modular, maintainable implementations.

Continue debugging independently without asking for confirmation for routine, non-destructive code fixes.

Stop and request guidance only when a decision requires external credentials, user authorization, significant architectural changes, or access to unavailable services.

These instructions apply to every subsequent development phase.
