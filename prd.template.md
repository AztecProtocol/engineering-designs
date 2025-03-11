# [Project Name] Project Requirements Document

- Owner:
- Approvers:
  - @[someone on product]
  - @[engineering team lead]
  - @[devrel engineer]
  - @[does this need the legal team?]
  - @[does this need the finance team?]
  - @[does this need the sales team?]
- Target PRD Approval Date: YYYY-MM-DD
- Target Project Delivery Date: YYYY-MM-DD

## Key words

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

## Background

Provide a high-level background for the project. Add links to any relevant documents rather than duplicating information (note, if linking to github, make sure to include the commit hash).

Explain what the status quo is and why it is inadequate.

## Key assumptions and dependencies

List the key assumptions made in creating the requirements.

List the key dependencies on other work streams or requirements.

For example, we assume that feature X will be complete by Y date, and that it will be cheaper to do Z than V.

## Desired User Flow(s)

Provide a high-level overview of the desired user flow.

There may be multiple user flows, and each flow should be in its own section.

Place the most important user flows first.

For example, if the project is about ensuring that upgrading to a new version of the rollup is "easy", focus on **who** you most want it to be easy for, and **what experience** you want them to have.

Each flow should discuss why you believe the user demands (or will tolerate) this experience.

### (Example) Easy Upgrades for End Users

When a new canonical version of the rollup is released, end users (e.g., wallet users) expect...

We know this because...

### (Example) Easy Upgrades for Validators

When a new canonical version of the rollup is released, validator operators expect...

We know this because...

## Requirements

Describe all the requirements you know of for the project which are relevant given the delivery deadline.

For example, if we were speccing an upgrade mechanism for a "regular database", we might have the following requirements:

### Functional Requirements (what the system does)

#### (Example) Data Migration Utility

- What: The system MUST include a utility that automatically migrates legacy schemas and data to the new database format.
- Why: To ensure a seamless transition with minimal manual intervention, preventing data loss or inconsistencies during the upgrade.
- Where: Derived from stakeholder interviews and an analysis of the current system’s limitations.

#### (Example) Backup and Rollback Mechanism

- What: The system MUST create a complete backup of the existing database and provide a rollback option in case of upgrade failures.
- Why: To safeguard against potential data corruption or upgrade errors, ensuring business continuity.
- Where: Based on IT risk assessments and business continuity planning guidelines.

### Non-Functional Requirements (qualities the system has)

#### (Example) Security Compliance

- What: The upgrade process MUST enforce encryption and strict access control measures to protect data in transit and at rest.
- Why: To protect sensitive information against unauthorized access and to comply with data protection regulations.
- Where: Sourced from regulatory requirements (e.g., GDPR, HIPAA) and security audits.

#### (Example) Maintainability

- What: Upgrade scripts and procedures SHOULD be modular and well-documented to facilitate future maintenance and troubleshooting.
- Why: To reduce long-term maintenance costs and ensure the system can be easily updated or modified.
- Where: Informed by best practices in IT service management and lessons learned from previous upgrade projects.

### Performance Requirements

#### (Example) Upgrade Speed

- What: The migration process MUST complete within a 4-hour maintenance window.
- Why: To minimize system downtime and avoid disruption to business operations during the upgrade.
- Where: Based on service level agreements (SLAs) and operational constraints set by the IT department.

#### (Example) Post-Upgrade Query Performance

- What: Average query response times MUST NOT exceed 200 milliseconds under normal load conditions.
- Why: To ensure that system performance meets user expectations and maintains efficient operations.
- Where: Derived from performance benchmarks established during testing and requirements from the performance engineering team.
- NOTE: Within the next 12 months, we will want this to be 100 milliseconds.

## Tradeoff Analysis

Include commentary on where the ideal candidate solution should sit in a tradeoff space, to give guidance how different candidate solutions will be compared. For example, stating that between two candidate solutions, the one that has the lower "cost measured in X" will be preferred.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
