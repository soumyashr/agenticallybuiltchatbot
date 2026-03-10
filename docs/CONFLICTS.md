# Spec vs Jira Conflicts Log

Last Updated: 2026-03-10

## Status: No Active Conflicts

No conflicts found between agent-spec `.md` files and Jira acceptance criteria.

**Reason:** All 62 Jira stories across 19 epics contain only user story descriptions
(As a... I want... So that...) with no separate acceptance criteria sections.
The spec files define implementation details (HOW) which do not contradict
the Jira user stories (WHAT).

## Observations

| UC | Observation | Recommendation |
|----|-------------|----------------|
| UC-04 | Jira stories describe version governance (drafts, archived, superseded). Spec 04_RAG_PIPELINE.md implements basic retrieval but not version filtering rules. | Add version governance config when UC-04 stories move to In Progress. |
| UC-05 | Jira stories describe multi-doc consolidation and user guidance. Spec handles multi-doc retrieval via RAG but lacks explicit consolidation UX. | Align implementation when UC-05 stories are prioritized. |
| UC-11 | Jira stories describe form guidance. No spec covers this UC explicitly. | Create new spec (e.g., 11_FORMS.md) when UC-11 stories move to In Progress. |
| UC-12 | Jira stories describe workflow prevention. No spec covers this UC explicitly. | Create new spec (e.g., 12_WORKFLOW_GUARD.md) when UC-12 stories move to In Progress. |
| UC-16 | Jira has 10 stories for Admin Console. Spec 07_ADMIN_API.md covers only document CRUD endpoints. | Significant gap — full admin console requires new spec when prioritized. |
| UC-17 to UC-19 | Jira has 3 additional epics (Multilingual, Academic Search, Cross-Department). No specs exist. | New epics discovered — specs needed when these enter development. |

## Rules

- Jira AC = WHAT (behavior) — wins on conflicts
- Spec .md = HOW (implementation) — wins on design decisions
- New conflicts must be logged here before any override
