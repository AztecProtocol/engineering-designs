# Engineering Process Project Requirements Document

- Owner: @just-mitch
- Approvers:
  - @joeandrews
  - @charlielye
  - @iAmMichaelConnor
  - @aminsammara
  - @0xrafi
  - @rahul-kothari
  - @LHerskind
  - @LeilaWang
  - @dbanks12
  - @PhilWindle
  - @nventuro
  - @Rumata888
  - @critesjosh
- Target PRD Approval Date: 2025-03-14

## Key words

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

## Introduction

- "Complex work" by engineering MUST have a Design Document (DD).
- Determining whether work is "complex" is the responsibility of engineering team leads and product managers. Good candidates include:
  - Introduces new concepts, data structures, algorithms, services, or contracts
  - Interface or protocol changes
  - Affects multiple products or users (including internal and external)
  - Major refactoring or restructuring of code
- A Design Document MUST have an associated Project Requirements Document (PRD).
- PRDs and DDs MUST be kept up to date via pull requests.
- Changes to the requirements in a PRD require re-approval by the individuals or groups specified in the original PRD.
- Changes to the design which affect its compliance with the PRD MUST be re-approved by the individuals or groups specified in the original PRD.

## Project Requirements Document (PRD)

- A PRD MUST be created as a pull request.
- A PRD MUST be a single document in a new directory in the `docs` directory.
  - For example, if the project is called `cool-user-flow`, the PRD should be in `docs/cool-user-flow/prd.md`.
  - A PRD MUST be written in markdown.
- A PRD MUST identify:
  - The project name
  - The person responsible for the project
  - Any individuals or groups that must approve the PRD.
    - This MUST include
      - someone on product
      - an engineering team lead
      - a devrel engineer if the project touches external stakeholders
    - This MAY include
      - someone from the legal team
      - someone from the finance team
      - someone from the sales team
  - The PRD's target approval date
  - The delivery deadline for the project
  - The main user stories the project is intended to support
  - How/If demand for those user stories has been measured
  - Requirements describing the desired functionality/qualities in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119) terms
  - Each requirement SHOULD identify:
    - Why the requirement exists
    - Where the requirement comes from (e.g. what user is asking for it, or other observation inspired the requirement)
    - The KPIs and target values that candidate solutions will be measured against
  - Each requirement MAY:
    - Give guidance on how the requirement may change beyond the delivery deadline
- The PRD SHOULD:
  - Define any key terms used in the requirements
  - Include a list of assumptions made in creating the requirements
  - Include a list of dependencies on other requirements
  - Include commentary on where the ideal candidate solution should sit in a tradeoff space, to give guidance how different candidate solutions will be compared. For example, stating that between two candidate solutions, the one that has the lower "cost measured in X" will be preferred.
- Once all required approvals have been received, the PRD SHOULD be merged within 72 hours.

## Design Document (DD)

- A DD MUST be created as a pull request.
- A DD MUST be a single document in a new directory in the `docs` directory.
  - For example, if the project is called `my-project`, the DD SHOULD be in `docs/my-project/dd.md`.
  - A DD MUST be written in markdown.
- A DD MUST identify:
  - The PRD (including the commit hash) that the DD supports
  - A title/name for the design
  - The design approach
  - The key architecture decisions
  - How the design is expected to perform against the requirements in the PRD
  - A lead engineer for the project
  - A target completion date for the project
  - Any individuals or groups that must approve the DD.
    - This MUST include
      - at least 2 engineers **other than the lead engineer**
      - the product manager responsible for the project
    - This SHOULD include
      - individuals outside of product/engineering that approved the PRD
  - The DD's target approval date
- A DD SHOULD identify:
  - assumptions/trade-offs made in creating the design
  - dependencies on other documents
  - a test plan for the project
  - a timeline for the project
  - preliminary diagrams or performance metrics as appropriate
- Engineers SHOULD NOT start work on a DD until the PRD has been approved and merged.
- Engineers SHOULD only do enough engineering work prior to the DD approval to allow them to write a good DD.
- Once all required approvals have been received, the DD SHOULD be merged within 72 hours.

## PRD Template

See [prd.template.md](prd.template.md) for a template for PRDs.

## DD Example

See [dd.template.md](dd.template.md) for a template for DDs.
