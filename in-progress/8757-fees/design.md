# Testnet Fees

|                      |                                                                    |
| -------------------- | ------------------------------------------------------------------ |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8757        |
| Owners               | @just-mitch @LHerskind                                             |
| Approvers            | @Maddiaa0 @PhilWindle @dbanks12 @nventuro @joeandrews @aminsammara |
| Target Approval Date | 2024-10-24                                                         |

## Mana and Costs

Refer to the unit of work on L2 as "mana", analogous to gas on L1. This has been referred to as "L2 gas" in the past.
This is also separate from the notion of "fee juice", which is conceptually a token with a balance, analogous to ETH.

In this document, we will use the term "fee asset" to refer to the unit of account for fees; that is, a transaction accumulates a cost in mana, which is converted to the fee asset according to the current price of mana.

A transaction incurs the following costs:
1. Proposers/validators simulate the transaction
2. Proposers publish pending blocks to L1
3. Proposers/validators/nodes update their state
4. Provers generate the avm proofs for the transaction
5. Provers generate the rollup proofs for the blocks/epoch
6. Provers verify the epoch proof on L1

Some costs are independent of the computation or data of the transaction itself, specifically numbers 2, 4, and 5; regardless, they must be covered by the transaction.

## Protocol Defined Constants

- `OVERHEAD_MANA_PER_TX` - the overhead cost in mana for a transaction (e.g. 21_000)
- `TARGET_MANA_PER_BLOCK` - the amount of mana that an "average" block is expected to consume (e.g. 15e6)
- `BLOBS_PER_BLOCK` - the number of blobs per block that are compensated for in the base fee (e.g. 3)
- `L2_SLOTS_PER_L2_EPOCH` - the number of L2 slots in each L2 epoch (e.g. 32)
- `L1_GAS_PER_BLOCK_PROPOSED` - the amount of L1 gas required to propose an L2 block on L1 (e.g. 0.2e6)
- `L1_GAS_PER_EPOCH_VERIFIED` - the amount of L1 gas required to verify an L2 epoch on L1 (e.g. 1e6)
- `MINIMUM_PROVING_COST_PER_MANA` - the minimum cost in wei for proving a unit of mana (e.g. 100)
- `MAXIMUM_PROVING_COST_PERCENT_CHANGE_PER_BLOCK` - the maximum percentage increase in the cost of proving a unit of mana per block (e.g. 1%)
- `PROVING_COST_PRECISION` - the precision of the `proving_cost_modifier` (e.g. 1e9)
- `MINIMUM_FEE_ASSET_PRICE` - the minimum price in wei of the fee asset (e.g. TST)
- `MAXIMUM_FEE_ASSET_PRICE_PERCENT_CHANGE_PER_BLOCK` - the maximum percentage increase in the price of the fee asset per block (e.g. 1%)
- `FEE_ASSET_PRICE_PRECISION` - the precision of the `fee_asset_price_modifier` (e.g. 1e9)
- `UNDERLYING_BASE_FEE_ORACLE_UPDATE_INTERVAL` - the minimum number of slots between updates to the underlying base fee oracle (e.g. 4)
- `MINIMUM_CONGESTION_MULTIPLIER` - the minimum value the congestion multiplier can take (e.g. 1)
- `CONGESTION_MULTIPLIER_DAMPER` - the constant factor to dampen movement in the congestion multiplier (e.g. 8.547)
- `MAXIMUM_EPOCH_PROOF_QUOTE_FEE` - the maximum basis point fee a prover can submit for an epoch proof quote (e.g. 9000)

## Block Header Fields

- `total_mana_used` - the total mana used by the block
- `excess_mana` - the running total of excess mana on the chain relative to `TARGET_MANA_PER_BLOCK`
- `base_fee_asset_per_mana` - the base fee in fee asset per mana

## Rollup Contract Fields

- `proving_cost_modifier` - a value used in the computation of the proving cost per mana
- `proving_cost_modifier_delta` - an "oracle" used to update the `proving_cost_modifier` from the previous block
- `fee_asset_price_modifier` - a value used in the computation of the fee asset price per wei
- `fee_asset_price_modifier_delta` - an "oracle" used to update the `fee_asset_price_modifier` from the previous block
- `wei_per_l1_gas` - the cost of L1 gas in wei. Updated by anyone to the current L1 gas price at most every `UNDERLYING_BASE_FEE_ORACLE_UPDATE_INTERVAL` slots
- `wei_per_l1_blob_gas` - the cost of L1 blob gas in wei. Updated by anyone to the current L1 blob gas price at most every `UNDERLYING_BASE_FEE_ORACLE_UPDATE_INTERVAL` slots

## Block Execution Cost

The cost of a block's execution in wei is equal to the following:
```math
\begin{aligned}
\text{execution gas} &= \text{L1 GAS PER BLOCK PROPOSED}  \\
&+ \text{BLOBS PER BLOCK} * \text{POINT EVALUATION PRECOMPILE GAS} \\
&+ \frac{\text{L1 GAS PER EPOCH VERIFIED}}{\text{L2 SLOTS PER L2 EPOCH}} \\
\text{execution wei} &= \text{execution gas} * \text{wei per l1 gas}
\end{aligned}
```

## Block Data Cost

The cost of a block's data in wei is equal to the following:

```math
\text{data wei} = \text{BLOBS PER BLOCK} * \text{GAS PER BLOB} * \text{wei per l1 blob gas}
```


## Exponentially Computed Values 

There are 3 important variables that are computed exponentially:
- `proving_cost_wei_per_mana`
- `fee_asset_per_wei`
- `base_fee_wei_per_mana_congestion_multiplier`

The purpose is to allow prices to fluctuate, but with guarantees, e.g. the proving cost in wei per mana will never change by more than X% per block.

All three computations follow the same formula:

```math
\text{value} = \text{minimum value} * \text{exp}\left(\frac{\text{variable}}{\text{constant}}\right)
```

### Example Calculation

[See a calculation](https://www.wolframalpha.com/input?i=%28exp%28%281e9%2B1e9%29%2F%281e9*100%29%29-exp%28%281e9%29%2F%281e9*100%29%29%29%2Fexp%28%281e9%29%2F%281e9*100%29%29) which shows the percent change if the numerator doubles from 1e9 to 2e9 when the denominator is 1e9*100 is ~1%. 

You can repeat the calculation for [a starting point of zero](https://www.wolframalpha.com/input?i=%28exp%28%281*1e9%29%2F%281e9*100%29%29-exp%28%280%29%2F%281e9*100%29%29%29%2Fexp%28%280%29%2F%281e9*100%29%29) to see that the percent change is ~1% as well.

The takeaway is that, in this case, if we cap the change in the numerator between 0 and 1e9, the percent change is at most ~1%.

### `proving_cost_wei_per_mana`

```math
\text{proving cost wei per mana} = \text{MINIMUM PROVING COST PER MANA} * \text{exp}\left(\frac{\text{proving cost modifier}}{100*\text{PROVING COST PRECISION}}\right)
```

A proposer can adjust the `proving_cost_modifier` stored in the rollup contract by up to `MAXIMUM_PROVING_COST_PERCENT_CHANGE_PER_BLOCK` each slot.

They do so by updating the `proving_cost_modifier_delta` field, which is used to update the `proving_cost_modifier` stored in the rollup contract.

That is,

```math
\text{new proving cost modifier} := \text{old proving cost modifier} + \text{proving cost modifier delta}
```

The new `proving_cost_modifier_delta` is capped at `MAXIMUM_PROVING_COST_PERCENT_CHANGE_PER_BLOCK` * `PROVING_COST_PRECISION`.


### `fee_asset_per_wei`

```math
\text{fee asset per wei} = \text{MINIMUM FEE ASSET PRICE} * \text{exp}\left(\frac{\text{fee asset price modifier}}{100*\text{FEE ASSET PRICE PRECISION}}\right)
```

A proposer can adjust the `fee_asset_price_modifier` stored in the rollup contract by up to `MAXIMUM_FEE_ASSET_PRICE_PERCENT_CHANGE_PER_BLOCK` each slot.

They do so by updating the `fee_asset_price_modifier_delta` field, which is used to update the `fee_asset_price_modifier` stored in the rollup contract.

That is,

```math
\text{new fee asset price modifier} := \text{old fee asset price modifier} + \text{fee asset price modifier delta}
```

The new `fee_asset_price_modifier_delta` is capped at `MAXIMUM_FEE_ASSET_PRICE_PERCENT_CHANGE_PER_BLOCK` * `FEE_ASSET_PRICE_PRECISION`.

### `base_fee_wei_per_mana_congestion_multiplier`

First we compute the excess mana in the current block by considering the parent mana spent and excess mana.

```math
\text{excess mana} = \begin{cases} 
0 & \text{if } \text{parent.excess} + \text{parent.spent} < \text{block.target} \\
\text{parent.excess} + \text{parent.spent} - \text{block.target} & \text{otherwise}
\end{cases}
```

```math
\text{base fee wei per mana congestion multiplier} = \text{MINIMUM CONGESTION MULTIPLIER} * \text{exp}\left(\frac{\text{excess mana}}{\text{target mana per block} * \text{CONGESTION MULTIPLIER DAMPER}}\right)
```

## Deriving the base fee

When a proposer is building a block, it calculates:
```math
\begin{aligned}
\text{block cost in wei} &= \text{execution wei} + \text{data wei} \\
\text{block cost in wei/mana} &= \frac{\text{block cost in wei}}{\text{target mana per block}} + \text{proving cost wei per mana} \\
\text{base fee in wei/mana} &= \text{block cost in wei/mana} * \text{base fee wei per mana congestion multiplier} \\
\text{base fee in fee asset/mana} &= \text{base fee in wei/mana} * \text{fee asset per wei}
\end{aligned}
```

This final value is the `base_fee_asset_per_mana` field in the L2 block header.

## The cost of a transaction in the fee asset

The amount of mana a transaction consumes is:

```math
\text{mana}_{tx} = \text{OVERHEAD MANA PER TX} + \sum_{op \in tx} \text{mana per operation}(op)
```

Therefore, the cost of a transaction's proposal, data publication, and verification at time $i$ is, denominated in the fee asset:

```math
\text{fee asset}_{tx} = \text{mana}_{tx} * \text{base fee asset per mana}
```

## Distribution of the fees

When a transaction is included in a block in the pending chain, the L2 balance of the fee asset for the `fee_payer` of the transaction is reduced by the transactions's fee asset cost.

When an epoch is proven, the fees for the epoch are paid out to each proposer for the block(s) they proposed.

A percentage of each block's fee asset fees are paid to the prover of the epoch. The percentage is determined based on the quote submitted by the prover for the epoch.

This quote is submitted by the prover in epoch `i+1` to prove epoch `i`, and is thus claimed/submitted to L1 by a proposer in epoch `i+1`.

In order to prevent a prover bribing a proposer into accepting a quote with an extremely high fee, the maximum fee a prover can submit for an epoch proof quote is `MAXIMUM_EPOCH_PROOF_QUOTE_FEE`.

## Clarifications and considerations

### Why is `blobs_per_block` a constant?

It makes computation easier. Otherwise block builder would need to know the number of blobs consumed by the transaction while it is building.

### L1 Congestion

If L1 gas spikes during an epoch, this will be reflected in the `wei_per_l1_gas` and `wei_per_l1_blob_gas` oracles and make their way into the cost.

However, these oracles lag the current L1 base fees. Furthermore, the base fee computed at the time of a block being proposed may differ from the base fee at the time of the epoch being verified.

Thus, it is possible for L1 gas prices to spike to a point where it is not profitable for a prover to submit their proof to L1. There are two retorts:
1. The prover should bake in a risk premium to compensate them for this risk; it is similar to the risk that the price of fee asset relative to any other asset shifts against them.
2. The prover can wait until the end of the epoch waiting for a less congested window to submit their proof to L1.

### Not charging for DA separately

By effectively charging each proposed block as though it uses BLOBS_PER_BLOCK blobs, we can simplify by not charging separately for DA, and instead add the use of the blobs directly to the block cost.

Regardless, the AVM supports DA gas metering per opcode, so it would not be difficult to add in the future if we change our mind.

Further, it is assumed that the proving cost will dominate the cost of the transaction, so this simplification makes implementation easier, and UX better.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [x] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [x] Private Kernel Circuits
- [x] Sequencer
- [x] AVM
- [ ] Public Kernel Circuits
- [x] Rollup Circuits
- [x] L1 Contracts
- [ ] Prover
- [x] Economics
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
