# The Design-Driven Development Process

During a sprint planning meeting, the team will discuss whether any of the issues to be worked on require a design document.

Something likely qualifies for a design document if it:

- Creates or changes an interface
- Introduces new concepts, data structures, or algorithms

If so, the owner of the issue will:

1. **Create a new design document in `./in-progress`**:
   - Follow the naming convention `NNNN-title.md`
       - `NNNN` is the issue number
       - `title` is a short description of the design (in `kebab-case`).


2. **Establish initial approvers**:
   - The first approver is your team lead. If you are a team lead, choose another approver.
   - If you are an approver, you can add other approvers or remove yourself as needed.
   - Work with your first approver to identify other approvers and stakeholders.

3. **Collaborate and iterate on the design document**:
   - Create and refine the first draft, then submit a PR
   - When you are ready, share the PR in the #engineering-designs channel in slack.
     - Include the design approvers, stakeholders, and the target approval date in your message
     - e.g.: [feature]. [target approval date]. cc @alice, @bob, @carol"
     - Open the thread and paste the "Executive Summary" from your design.
   - Iterate on the design based on the feedback and discussions

4. **Get approval**:
   - When approvers are satisfied with the design, they will approve the PR on github.
   - When all approvers have signed off, merge the PR with the design

5. **Implement the design** based on the finalized design document.
   - Any changes or decisions made during the implementation phase should be captured in user docs or protocol spec *and flagged in PRs*.
   - When the design has been implemented, create a PR to move it from `./in-progress` to `./implemented`
       - Include a brief explanation of changes to the original design


If a design is ultimately rejected, the owner should update PR to merge the design document into the `./rejected` directory after adding a comment explaining why it was rejected.

If a design is approved for implementation and then abandoned, the owner should create a PR to move it from `in-progress` to `abandoned` after adding a comment explaining why the design was abandoned.

 
## Approvers vs Stakeholders

Stakeholders are anyone materially impacted by your change. This should be a large-ish set: PMs, DevRel, engineers across the stack, so on. Shoot for at least 5 stakeholders.

Approvers are a subset intimately familiar with what you're doing who will share the responsibility for the outcomes from the design. Shoot for 2-5 approvers. 

## Rejected Designs

If a design is ultimately rejected, the untag the document with `design-wip`, and tag it with `design-rejected`. Include a brief explanation of why the design was rejected.

Note, rejected designs are good. It saves us from implementing bad designs, and allows us to point back at why certain decisions were made.


## Zen-spiration

Why do we care about designs?

> "The beginning is the most important part of the work." - Plato

A design means we can move faster because we all have more clarity on what we're building and how all the users interact.

> "Design is not what you see, but what you make others see." - Edgar Degas

Speed is paramount: it allows us to more rapidly provide value to users, and refine that value.

> "Design is an iterative process. The key is to generate ideas, test them, and iterate until you find the right solution." - John Maeda

Designs are solutions to problems. Problems are experienced by users. Therefore, a design-driven mindset is a user-centric mindset.

> "The role of the designer is that of a good, thoughtful host anticipating the needs of his guests." - Charles Eames

Users include end-users, external developers, internal developers, and even/especially components of the system itself. When we think about designing components as users, we can think about the "primitives" that we need.

> "Primitives are the raw parts or the most foundational-level building blocks for software developers. They’re indivisible (if they can be functionally split into two they must) and they do one thing really well. They’re meant to be used together rather than as solutions in and of themselves. And, we’ll build them for maximum developer flexibility. We won’t put a bunch of constraints on primitives to guard against developers hurting themselves.  Rather, we’ll optimize for developer freedom and innovation." - 2003 AWS Vision document

Keeping yourself in a purposeful, user-centric mindset is a discipline.

> "Quality is not an act, it is a habit." - Aristotle


# Template

|                      |                                   |
| -------------------- | --------------------------------- |
| Issue                | [title](github.com/link/to/issue) |
| Owners               | @you                              |
| Approvers            | @alice @bob                       |
| Target Approval Date | YYYY-MM-DD                        |


## Executive Summary

Provide the executive summary on your major proposed changes.

## Introduction

Briefly describe the problem the work solves, and for whom. Include any relevant background information and the goals (and non-goals) of this implementation.

## Interface

Who are your users, and how do they interact with this? What is the top-level interface?

## Implementation

Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces.

Discuss any alternative or rejected solutions.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] Fees
- [ ] P2P Network
- [ ] DevOps

## Test Plan

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.

## Documentation Plan

Identify changes or additions to the user documentation or protocol spec.


## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
