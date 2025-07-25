# Dyson Protocol Agent Guide

## Build & Test Commands
- `make install` - Build and install dysond binary (required before testing/running)
- `make dysvm` - Build custom Python VM (run first after clone)
- `make test PYTEST_ARGS="tests/<the test file>::<the test function> --ff --nf -xs"` - Run Python pytest integration tests (will automatically build and install dysond first)
- `make init` - Initialize single chain with 2 nodes for development
- `make start` - Start development blockchain with logs
- `make init-localnet` - Initialize 2 chains with IBC for cross-chain testing
- `make start-localnet` - Start multi-chain testnet
- `make proto-gen` - After changing anything in ./proto dir, regenerate the go types and schema files
- `DEFAULT_BASE_DIR=/tmp/test-dysonchains python -m pytest tests/test_FILE.py::test_function -xs` - Run single Python test without building or installing dysond

## Architecture
- **Core**: Cosmos SDK-based blockchain with custom modules in x/ (storage, script, crontask, nameservice, nft)
- **DYSVM**: Custom Python VM with embedded Python 3.12+ runtime for on-chain script execution
- **Key modules**: x/storage (on-chain data), x/script (Python execution), x/crontask (scheduled tasks), x/nameservice (domain market)
- **Testing**: Python pytest integration tests with chainnet.py orchestration, all tests are in the `tests/` directory, not using go tests
- **Client**: dysond CLI binary for transactions and queries

## Code Style
- **Go**: Standard Cosmos SDK patterns, collections framework for state, keeper pattern
- **Imports**: cosmossdk.io/* grouped first, then github.com/cosmos/*, then project imports (dysonprotocol.com/*)
- **Testing**: pytest with fixtures for integration tests
- **Types**: Protobuf-generated types in types/ directories
- **Error handling**: cosmossdk.io/errors for wrapped errors with codes
- **Naming**: CamelCase for exported, camelCase for private, snake_case in Python
- **State**: Use collections.Map/Item for robust state management, prefix separation


# AI Coding Agent Policy Document

## 1\. Introduction

### 1.1. Purpose

This document outlines the coding policy that any human or AI Coding Agent (hereafter "AI Agent") must strictly adhere to when making changes to a codebase. It covers scoping features via Product Backlog Items (PBIs) and managing the tasks required to implement those features. This policy ensures a disciplined, transparent, and human-controlled approach to software development.

This document should be stored in a project's documentation directory, `./delivery/` , separate from user-facing documentation.

### 1.2. Actors

* **User (Human Manager):** The individual responsible for defining requirements, prioritising work, approving changes, and ultimately accountable for all code modifications. The User makes all final decisions regarding scope and design.  
* **AI Agent:** The delegate responsible for executing the User's instructions precisely as defined by PBIs and tasks.

This policy is primarily for the AI Agent, operating under the User's strict guidance. If any aspect of this policy or a given instruction is unclear, the AI Agent must initiate a conversation with the User for clarification.

## 2\. Fundamental Principles

1. **Task-Driven Development:** No code shall be changed in the codebase unless there is an agreed-upon task explicitly authorizing that change.  
2. **PBI Association:** No task shall be created unless it is directly associated with an agreed-upon Product Backlog Item (PBI).  
3. **PRD Alignment (if applicable):** If a Product Requirements Document (PRD) is linked to the product backlog, PBI features must be sense-checked to ensure they plausibly align with the PRD's scope. Discrepancies must be raised with the User.  
4. **User Authority:** The User is the sole decider for the scope and design of ALL work. Delegation to an AI Agent does not transfer this authority or responsibility.  
5. **User Responsibility:** Responsibility for all code changes remains with the User, regardless of whether the AI Agent performed the implementation.  
6. **Prohibition of Unapproved Changes:** Any changes outside the explicit scope of an agreed task are EXPRESSLY PROHIBITED. This includes:  
   * **Unapproved "Optimizations":** If an AI Agent identifies a potential optimization outside the current task's scope, it must propose this as a new, separate task for User prioritisation. It should not implement the optimization proactively.  
   * **Unapproved Out-of-Scope Work:** This includes any other changes, deletions, or additions not explicitly defined in the agreed task.  
7. **Managing Accidental Scope Creep:** Language models are not perfect, and unintended changes might occur. To defend against this:  
   * Always work against a specific, agreed task.  
   * Before finalizing work, re-verify the task scope.  
   * Perform a code diff and review all changes line-by-line against the task scope.  
   * If any code change is identified as outside the task scope (scope creep):  
     * A note must be made identifying the scope creep.  
     * The changes for the task must be rolled back entirely.  
     * The task must be re-attempted, ensuring strict adherence to scope.  
   * Repeat this process until the implemented changes are 100% unambiguously linked to the task's defined scope.  
8. **Integrity and Sense-Checking:** The AI Agent is expected to critically evaluate instructions against this policy. If instructions appear mistaken, conflicting, or violate the spirit of this policy, the AI Agent must pause and initiate a conversation with the User, presenting its questions or observations.  
9. **Comprehensive Logging:** All significant actions and changes related to PBIs and tasks must be logged in their respective History sections.  
10. **Solution Options Requirement:** When the User requests a code change, the AI Agent must suggest three solution options for the User to consider:
    * **Quick Direct Solution:** A straightforward, minimal change that directly addresses the request with the least complexity or overhead.
    * **Idiomatic Solution:** An approach that follows best practices and conventions for the relevant language, framework, or ecosystem, balancing clarity and maintainability.
    * **Robust Professional Solution:** A comprehensive, production-quality approach that anticipates edge cases, includes error handling, documentation, and is suitable for long-term maintainability.
    The AI Agent must briefly describe each option and, if appropriate, recommend one based on the context. The User will select the preferred approach before implementation proceeds.

## 3\. Product Backlog Item (PBI) Management

### 3.1. Overview

All changes to the product are defined by a set of Product Backlog Items (PBIs). These PBIs are built in the order specified in the product backlog.

### 3.2. The Backlog Document

* The product backlog is wholly defined within a single Markdown document, by default located at `./delivery/backlog.md`.  
* **Scope and Purpose:** The document should begin with a "Scope and Purpose" section, describing what the backlog covers (e.g., "All features for this repository" or linked to a specific PRD).

### 3.3. Backlog Structure

The `backlog.md` file contains 3 main sections:

1. **"Not Done" PBIs Table:**
   - PBIs are ordered by priority (top = highest priority)
   - Status column determines workflow state (Proposed/Agreed/In Progress/In Review)
   ```markdown
   | ID | Actor | User Story | Status | Conditions of Satisfaction (CoS) |
   |---|---|---|---|---|
   ```

2. **"Done" PBIs Table:**
   ```markdown
   | ID | Actor | User Story | Status | Conditions of Satisfaction (CoS) |
   |---|---|---|---|---|
   ```

3. **PBI History Log:**
   ```markdown
   | Timestamp (YYYYMMDD-HHMMSS) | PBI ID | Event Type | Details | User |
   |---|---|---|---|---|
   ```

Key Principles:
- Status is maintained ONLY in the Status column
- Priority is determined by vertical ordering (higher in table = higher priority)
- No redundant "Group" headers are used

### 3.4. PBI Data Fields

Each PBI must include these REQUIRED fields:

* **ID:** 
  - Numerical only (e.g., 1, 2, 3)
  - Example: `1`

* **Actor:** 
  - Who benefits from the feature
  - Example: `User`, `Admin`, `System`

* **User Story:** 
  - Format: "As a [Actor], I want [action] so that [benefit]"
  - Example: `As a User, I want to create a website with just a URL...`

* **Status:** 
  - One of: Proposed, Agreed, In Progress, In Review, Done
  - Must match PBI's group in backlog

* **Conditions of Satisfaction (CoS):**
  - 3-5 testable acceptance criteria
  - Markdown bullet points
  - Example:
    ```markdown
    1. User can enter just URL when clicking 'New website'
    2. No validation errors for other fields
    3. Website appears immediately in list
    ```

These fields must appear EXACTLY as specified in ALL PBI tables.

### 3.5. PBI Workflow and Status Transitions

1. **PBI Statuses:**  
   * **Proposed:** An idea for a feature. Not to be developed …yet.  
   * **Agreed:** Approved by the User for development, subject to prioritisation in backlog. Must have one or more tasks planned before work can begin.  
   * **In Progress:** Actively being worked on (i.e., at least one associated task is "In Progress").  
   * **In Review:** All associated tasks are "Done." The PBI is awaiting User review and final approval.  
   * **Done:** The User has approved the PBI. Work is considered complete and immutable. Changes after a PBI has moved to "done" require a new PBI.

   

2. **PBI Event-Driven Transitions:**  
     
   * **Event: New Feature Idea (User/AI Discussion or AI Initiative)**  
     1. A new PBI is created with a unique ID.  
     2. Status is set to **Proposed**.  
     3. The PBI is added to the bottom of the "Proposed" group in the "Not Done" table.  
     4. The AI Agent must check for overlap with existing PBIs (both "Done" and "Not Done"). If overlap is suspected, discuss with User before adding.  
   * **Event: User Approves a "Proposed" PBI**  
     1. Status changes: **Proposed** \=\> **Agreed**.  
     2. The PBI is moved to the bottom of the "Agreed" group.  
     3. AI Agent prompts User to confirm priority within the "Agreed" group (e.g., "Move before PBI \#15" or "Move to top of 'Agreed'").  
     4. AI Agent checks if tasks exist for this PBI. If not, it prompts the User to initiate task planning, as a PBI cannot be actioned without tasks.  
   * **Event: AI Agent Starts Work on the First Task of an "Agreed" PBI**  
     1. PBI Status changes: **Agreed** \=\> **In Progress**.  
     2. The PBI is moved to the bottom of the "In Progress" group (or as per User-defined priority within this group).  
   * **Event: AI Agent Completes All Tasks for an "In Progress" PBI**  
     1. PBI Status changes: **In Progress** \=\> **In Review**.  
     2. The PBI is moved to the bottom of the "In Review" group.  
     3. AI Agent notifies the User that the PBI is ready for review, summarizing the work done.  
     4. AI Agent proceeds to the next highest priority task, which might be for another "In Progress" PBI or start a new "Agreed" PBI.  
   * **Event: User Reviews and Approves an "In Review" PBI**  
     1. PBI Status changes: **In Review** \=\> **Done**.  
     2. The PBI is moved from the "Not Done" table to the top of the "Done" table.  
   * **Event: User Reviews an "In Review" PBI and Finds Issues**  
     1. PBI Status remains **In Review**.  
     2. A conversation occurs with the AI Agent to create new tasks to address the issues. The PBI cannot move to "Done" until these new tasks are also completed and the User is satisfied.  
   * **Event: Bug Found in a "Done" PBI**  
     1. "Done" PBIs are immutable. A new PBI must be created to address the bug.  
     2. This new PBI starts as **Proposed** and is added to the bottom of the "Proposed" group, to be prioritised by the User.  
   * **Event: User Deprioritises an "In Progress" or "Agreed" PBI**  
     1. If "In Progress": All associated active tasks are stopped. Task statuses revert to "Agreed." PBI Status changes: **In Progress** \=\> **Agreed**.  
     2. The PBI is re-prioritised within the "Agreed" group by the User.  
   * **Event: User Needs to Split a PBI (Scope Change)**  
     1. A conversation occurs with the AI Agent to define the scope split.  
     2. The original PBI's "User Story" and "CoS" are updated to reflect the reduced scope. Its ID and existing completed tasks remain.  
     3. A new PBI is created for the carved-out scope. It gets a new unique ID, status **Proposed**, and is added to the bottom of the "Proposed" group for User prioritisation.  
   * **NO OTHER PBI STATUS TRANSITIONS ARE PERMITTED.**

### 3.6. PBI History Log

* Located at the bottom of the `backlog.md` document.  
* Records all changes to PBIs.  
* Columns:  
  * **Timestamp (YYYYMMDD-HHMMSS):** Sortable, most recent first.  
  * **PBI ID:** The ID of the PBI affected.  
  * **Change Description:** Free-form text explaining the change (e.g., "Status to Agreed", "Split into PBI \#X", "User Story updated").

### 3.7. Backlog Setup

If the User requests to "create a backlog," the AI Agent will:

1. Create an empty `./delivery/backlog.md` file.  
2. Populate it with the standard "Scope and Purpose" header and empty "Not Done" and "Done" PBI tables (with headers).  
3. Include an empty "PBI History Log" table.  
4. Encourage the User to add initial PBIs.

## 4\. Task Management

### 4.1. Core Principles

1. **PBI Decomposition:** PBIs are broken down into one or more tasks. Code changes are made ONLY by executing these tasks.  
2. **Strict Scope Adherence:** All work done for a task must strictly adhere to that task's defined scope. No changes outside this scope are permitted (see Fundamental Principle \#6).  
3. **Task Granularity:** Tasks should be small enough to be completed and tested independently, ideally within a short timeframe.  
4. **Plan Adherence:** All work must strictly follow the tasks outlined in the relevant PBI's task file.

### 4.2. Task Planning for a PBI

1. Two files are created for each PBI:
   - `<PBI-ID>/<PBI-ID>-tasks.md`: Task list table (existing format)
   - Individual task files `<PBI-ID>/<PBI-ID>-<TASK-ID>.md` with:

2. The PBI row in `backlog.md` must link to its task list:
   ```markdown
   | 1 | User | [Create website with URL only](./1/1-tasks.md) | Proposed | ... |
   ```

### 4.6. Detailed Task Documentation

Each task requires a standalone file with this exact structure:
```markdown
# [Task-ID] [Task-Name]

## Analysis
- **Purpose:** 1-2 sentence task rationale
- **Non-functional Considerations:**
  - Security:
  - Performance:
  - Observability:
  - etc.
- **Business Rules:**

## Design
- **Technical Specifications:**
- **Architectural Compliance:**

## Testing
- **Test Cases:**
- **Test Data Requirements:**

## Change Plan
- **Files to Modify:**
- **Implementation Approach:**
```

Key Rules:
- Files must stay synchronized with the main task table
- Use UK English throughout
- No deviations from this structure

The task table must link to each detailed task file:
```markdown
| 1-1 | [Analyse requirements](./1-1.md) | Proposed | ... |
```

Each detailed task file must link back to:
- The main task list (`[Back to task list](./1-tasks.md)`)
- The parent PBI (`[View Backlog](../backlog.md#user-content-1)`)

Linking Rules:
1. Use relative paths from current directory
2. Label backlog links as "View Backlog"
3. Maintain consistent anchor format (#user-content-<PBI-ID>)

### 4.3. Task Data Fields

Each task in the PBI's task file must have:

* **Task ID:** 
  - Format: `<PBI-ID>-<TASK-NUMBER>` (e.g. `1-1`, `1-2` for tasks under PBI 1)
  - Must be unique within the PBI
  - Numbers sequential starting from 1
  - Example: `2-35` for the 35th task in PBI 2
* **Description:** What needs to be done
* **Status:** Current state (Proposed/Agreed/In Progress/Done)
* **Test Criteria:** How completion will be verified

### 4.4. Task Orthogonality and Conflicts

* Tasks should be orthogonal (scopes should not overlap).  
* If an overlap is identified between planned tasks, they must be refactored into distinct, prerequisite tasks.  
* If a conflict arises between tasks, the AI Agent must not proceed but escalate to the User with suggested resolutions.

### 4.5. Task Lifecycle and Workflow

1. **Task Statuses:**  
   * **Proposed:** The initial state of a newly defined task.  
   * **Agreed:** The User has approved the task description and its place in the priority list. Work cannot begin unless "Agreed."  
   * **In Progress:** The AI Agent is actively working on this task. Only one task per PBI (or even per AI Agent globally, if preferred by User) should be "In Progress" at any time.  
   * **Review:** The AI Agent has completed the work for the task, including writing and passing tests. It awaits User validation.  
   * **Done:** The User has reviewed the task's implementation and deems it successfully completed.

   

2. **Task Event-Driven Transitions:**  
   * **Event: New Task Defined during PBI Task Planning**  
     1. A new task is added to the PBI's task file (`<PBI-ID>-tasks.md`).  
     2. Task ID is assigned (e.g., next available number for that PBI).  
     3. Status is set to **Proposed**.  
     4. It is added to the bottom of the task list for that PBI.  
   * **Event: User Agrees to a "Proposed" Task (and its priority)**  
     1. Status changes: **Proposed** \=\> **Agreed**.  
     2. The task is ordered by the User in the list of "Agreed" tasks for that PBI.  
   * **Event: AI Agent Selects an "Agreed" Task to Start Work (based on priority and PBI status "In Progress")**  
     1. **Repository Check:** AI Agent verifies the git repository is clean (no uncommitted changes). If not, HALT and notify User. (Skip if no git repo).  
     2. Task Status changes: **Agreed** \=\> **In Progress**.  
   * **Event: AI Agent Completes Work for an "In Progress" Task**  
     1. Code changes are made strictly within task scope.  
     2. Appropriate tests are written and pass.  
     3. Task Status changes: **In Progress** \=\> **Review**.  
     4. AI Agent notifies User that the task is ready for their review, summarizing changes and test results.  
   * **Event: User Reviews and Approves a "Review" Task**  
     1. Task Status changes: **Review** \=\> **Done**.  
     2. If this was the last task for the PBI, the PBI status changes to "In Review" (see PBI workflow).  
   * **Event: User Reviews a "Review" Task and Finds Issues**  
     1. Task Status changes: **Review** \=\> **In Progress** (or **Agreed** if significant rework/re-planning is needed, per User discretion).  
     2. The User provides feedback, and the AI Agent reworks the task.  
   * **Event: User Decides to Cancel or Deprioritise an "Agreed" or "In Progress" Task**  
     1. If "In Progress," work halts. Code changes are typically rolled back unless User specifies otherwise.  
     2. Task Status changes to **Proposed** (if cancelled for now) or re-prioritised within "Agreed."  
   * **NO OTHER TASK STATUS TRANSITIONS ARE PERMITTED.**

### 4.6. Task Execution by AI Agent (Summary)

2. Identify the current "In Progress" PBI.  
3. Select the highest-priority "Agreed" task from that PBI's task file. If no "Agreed" tasks, and PBI is "Agreed" (not "In Progress"), discuss with User about starting the PBI or task planning.  
4. Perform clean repo check.  
5. Change task status to "In Progress."  
6. Implement the changes strictly adhering to the task's scope.  
7. Write or update automated tests for the changes.  
8. Ensure all relevant tests pass.  
9. Commit changes with a clear message referencing the Task ID (e.g., "Fix: Implement user avatar upload as per task 7-3").  
10. Change task status to "Review."  
11. Notify the User.

### 4.7. Task Modification Rules

1. **Proposed Tasks**:
   - AI Agents may add, remove, or modify Proposed tasks when:
     - Emerging requirements are discovered
     - Technical dependencies are identified
     - Task decomposition is needed
   - Changes must be documented in the task's Analysis section

2. **Agreed Tasks**:
   - Require User approval for modification
   - AI may suggest changes via comments

3. **Change Documentation**:
   - All modifications must include:
     - Reason for change
     - Impact analysis
     - Timestamp

### 4.7. Task History Log

* Located at the bottom of each `<PBI-ID>-tasks.md` file.  
* Records all status changes and significant modifications to tasks for that PBI.  
* Columns:  
  * **Timestamp (YYYYMMDD-HHMMSS):** Sortable, most recent first.  
  * **Task ID:** The ID of the task affected.  
  * **Change Description:** Free-form text explaining the change (e.g., "Status to In Progress", "Description updated by User").

## 5\. General Technical Policies

1. **Method Signature Changes:** Modifying method/function signatures that are potentially used by other parts of the codebase requires extreme caution:  
   * A thorough impact assessment must be conducted to identify all call sites and potential side effects. This assessment should be documented.  
   * Explicit confirmation and approval from the User are required *before* implementing the change.  
   * This policy is critical for maintaining codebase stability and ensuring changes are deliberate and well-understood.  
2. **Test Coverage:** New features or changes should be accompanied by appropriate automated tests (unit, integration, etc.) to ensure correctness and prevent regressions. Tests must pass before a task is moved to "Review."  
3. **Code Comments and Documentation:** Code should be clear and understandable. Comments should explain *why* something is done, not *what* is done, if the code isn't self-explanatory. Update relevant internal documentation as part of the task.
