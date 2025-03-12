# PRD: Prover Submission Cost

- Owner: @LHerskind
- Approvers:
  - Product: @joeandrews, @aminsammara
  - Engineering: @just-mitch, @Maddiaa0
  - DevRel:
- Target PRD Approval Date: 2025-03-14
- Target Delivery Deadline: 2025-03-31

> [!NOTE]
> **Keywords**   
> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

# Background

> [!NOTE] 
> **Key Terms**   
> - **Multi-Proofs**: Scheme that allows redundancy in proof submission and shares payment between all submitters.
> - **Mana**: The unit of work on the Aztec rollup
> - **BaseFee**: The amount of fee asset to pay per _Mana_ to cover costs
> - **Congestion Multiplier**: A multiplier on top of the _BaseFee_ that depends on the usage of the chain to limit spam etc.

The act of producing blocks incurs a cost to the block builders:

- The sequencer pay for publishing the block to the data availability layer and to perform some validity checks such as validating attestations.
- The prover pays for producing the proof (proving) and then to publish the proof to the base-layer.

We build the background on assuming that you are familiar with the following past design docs:

- Prover Coordination Design([cdfb3a72](https://github.com/AztecProtocol/engineering-designs/blob/cdfb3a72e9b3e4415dcbfe04bd92878996472e6d/in-progress/8509-prover-coordination/design.md))
- Fee Design Doc ([dac7fdfb](https://github.com/AztecProtocol/engineering-designs/blob/dac7fdfbffb0b0d10ce0dff85221f7a6ece1933b/in-progress/8757-fees/design.md))

The _BaseFee_ was designed to cover:

1. the cost to prove the transactions in the block
2. the cost to submit the block
3. `1/N` cost to submit an epoch proof (`N` being epoch size)

The BaseFee calculation originally assumed sufficient mana utilization per block to meet targets. Therefore, blocks with low utilization would not fully cover operational costs through fees alone. To address this, block rewards were introduced as a subsidy.

Provers were compensated with a share of both fees and rewards, allocated according to their provided quotes.

Then the move to [Prover Coordination: Multiproofs](https://hackmd.io/Ivn9axP1SFyEHjpAXVn62g) happened and the costs morphed into the following (`M` is number of proofs):

1. the cost to prove the transactions in the block `M` times
2. the cost to submit the block
3. `M/N` cost to submit an epoch proof

However, our model is currently flawed as it is:

- not taking `M` proofs into account when computing the BaseFee
- paying the proof submission cost to the sequencer, not the prover

These flaws are remnants of the quote-based prover coordination.

## Assumptions

- There exists at least `M` provers that are willing to participate in block production.
  - If the true number is less than `M` we are overpaying for proofs.
- The gas estimates of the proof submission cost is somewhat precise
  - Even though it happens potentially many blocks before the proof submission itself.
- We expect submission cost to be greater than proving cost.

# User Stories

## End User

As an end user, I want transaction fees to be predictable, transparent, and low, similar to using a single-sequencer system, so that I don’t face unexpectedly high costs.

This is especially important during early network phases with low usage, when high fees might discourage me from continuing to use the network.

> [!WARNING]
> **Multi-proof overhead**   
> If the costs associated with submitting multiple proofs (M) are passed directly to users via the BaseFee, it may lead to significantly higher fees compared to centralized or single-proof setups. The additional application of the Congestion Multiplier on these inflated fees could further compound this issue, potentially causing users to abandon the network early on.

## Prover

As an economically rational prover, I wish to participate in block production on the Aztec network, such that I can earn some money on all the machines that I have collected.

In short, as a prover, I wish to:

1. Collect blocks and transactions as the chain grows
2. Run machines to prove transactions and roll them into an epoch proof
3. Submit epoch proofs to the base-layer for a share of the rewards
4. Profit???

> [!WARNING]
> **Multi-proof commentary**   
> With the nature of the multi-proofs splitting rewards between all submitters and only paying out after. We won't know if there is profit or not until ahead of time.

# Requirements

## Functional Requirements

### Earmarked Fees

- **What**: Fees earmarked for specific actions (e.g., proof submission) **MUST** be directed to the entity incurring the associated cost.
- **Why**: To maintain fairness and economic incentive alignment between actors.
- **Where**: Derived from the current imbalance (sequencer receives funds without bearing costs).

### Protection from Excessive Multi-Proof Costs

- **What**: Transaction fees charged to users **SHOULD** increase at most sub-linearly due to the introduction of multi-proof submissions compared to a single-proof sequencer setup.
- **Why**: To prevent users from experiencing unexpectedly high fees resulting from internal design decisions (such as multiple proofs), ensuring network adoption and retention.
- **Where**: Derived from concerns about potential abandonment during periods of low network utilization or initial adoption phases.

## Non-functional Requirements

### Prover profitability

- **What**: Proving **SHOULD** be profitable in the presence of `<=M` submitters, even during periods of low activity.
- **Why**: To ensure chain-growth and avoid avoid continuous pruning.
- **Where**: Derived from other requirements on stable block production and looking at other chains and general economics.

### Scalability

- **What**: In the presence of `<=M` submitters their profit **SHOULD** scale with increasing transaction volume and overall network usage.
- **Why**: To avoid creating incentives for provers and sequencers to collude, deliberately limiting network throughput to maximize their individual profits at the expense of network growth.
- **Where**: Derived from concerns regarding potential economic collusion.

### Inflation Bounds

- **What**: The inflation of the staking asset **MUST** be less than **X**
- **Why**: Infinite inflation is not scalable.
- **Where**: Common sense

> [!NOTE]
> **HELP**  
> What should **X** be @aminsammara

# Handling Tradeoffs

When handling the tradeoffs, I believe we should step in the direction of "subsidise too much".

For ignition there will be **no fees** since there are no transactions. If the provers cannot recoup their costs from the block rewards it is very limited who would be able **and** willing to participate.

For alpha, it will also allow us to keep transaction fees low(er) while usage is low, making is easier for users to try the network.
