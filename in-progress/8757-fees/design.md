# Testnet Fees

|                      |                                                                    |
| -------------------- | ------------------------------------------------------------------ |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8757        |
| Owners               | @just-mitch @LHerskind                                             |
| Approvers            | @Maddiaa0 @PhilWindle @dbanks12 @nventuro @joeandrews @aminsammara |
| Target Approval Date | 2024-10-24                                                         |

## Mana and Costs

Refer to the unit of work on L2 as "mana", analogous to gas on L1.

A transaction incurs the following costs:
1. Proposers/validators simulate the transaction
2. Proposers publish pending blocks to L1
3. Provers generate the avm proofs for the transaction
4. Provers generate the rollup proofs for the blocks/epoch
5. Provers verify the epoch proof on L1

Some costs are independent of the computation or data of the transaction itself, specifically numbers 2, 4, and 5; regardless, they must be covered by the transaction.

## Protocol Defined Constants

- `overhead_mana_per_tx` - the overhead cost in mana for a transaction
- `target_mana_per_block` - the amount of mana that an "average" block is expected to consume
- `blobs_per_block` - the number of blobs per block that are compensated for in the base fee
- `l2_slots_per_l2_epoch` - the number of L2 slots in each L2 epoch
- `l1_gas_per_block_proposed` - the amount of L1 gas required to propose an L2 block on L1
- `l1_gas_per_epoch_verified` - the amount of L1 gas required to verify an L2 epoch on L1
- `minimum_proving_cost_per_mana` - the minimum cost in wei for proving a unit of mana
- `maximum_proving_cost_multiplier_per_block` - the maximum percentage increase in the cost of proving a unit of mana per block
- `minimum_fee_asset_price` - the minimum price in wei of the fee asset (e.g. TST)
- `maximum_fee_asset_price_multiplier_per_block` - the maximum percentage increase in the price of the fee asset per block
- `underlying_base_fee_oracle_update_interval` - the minimum number of slots between updates to the underlying base fee oracle
- `congestion_factor_multiplier` - the constant factor to multiply the congestion factor by
- `maximum_epoch_proof_quote_fee` - the maximum fee a prover can submit for an epoch proof quote

## Oracles

### `fee_asset_per_wei`

This will be stored on the rollup contract. On proposing a block, proposers will be able to adjust the rate by up to `maximum_fee_asset_price_multiplier_per_block`.

Has a minimum value of `minimum_fee_asset_price`.

### `proving_cost_per_mana`

This will be stored on the rollup contract. On proposing a block, proposers will be able to adjust the rate by up to `maximum_proving_cost_multiplier_per_block`.

Has a minimum value of `minimum_proving_cost_per_mana`.

### `wei_per_l1_gas` and `wei_per_l1_blob_gas`

The rollup contract will maintain an `wei_per_l1_gas` oracle. 

Same for `wei_per_l1_blob_gas`.

They will be updated up to every `underlying_base_fee_oracle_update_interval` slots.


## Getting the cost of a block in wei/mana

When a proposer is building a block, it calculates the total L1 cost of the block in wei by summing:
- `l1_gas_per_block_proposed` * `wei_per_l1_gas`
- `blobs_per_block` * `GAS_PER_BLOB` * `wei_per_l1_blob_gas`
- `l1_gas_per_epoch_verified` * `wei_per_l1_gas` / `l2_slots_per_l2_epoch`

The cost of the block in wei/mana is then the sum of the following:
- the total L1 cost in wei divided by `target_mana_per_block`
- `proving_cost_per_mana`

## Getting the Base Fee in wei/mana

After simulating a block, the mana used by each transaction is known.

A proposer can compute a block's `total_mana_used` by summing the `mana_used` fields of all transactions in the block.

This `total_mana_used` will be part of the L2 block header.

The rollup contract will maintain a `excess_mana` variable for the proven and pending chains.

The `excess_mana` is computed from the previous block as the difference between `total_mana_used` and `target_mana_per_block`.

Compute the L2 congestion factor as the "fake exponential" of the ratio of `total_mana_used` plus the previous block's `excess_mana` to `target_mana_per_block`, and multiply by a constant factor of 1e9:

$$
\text{congestion factor} = \text{congestion factor multiplier} * \text{exp}\left(\frac{\text{total mana used} + \text{previous excess mana}}{\text{target mana per block}}\right)
$$

The base fee in wei/mana is then:
$$
\text{base wei per mana} = \text{congestion factor} * \text{cost of block in wei/mana}
$$


## The cost of a transaction in the fee asset

The amount of mana a transaction consumes is:
$$
\text{mana}_{tx} = \text{overhead mana per tx} + \sum_{op \in tx} \text{mana per operation}(op)
$$

Therefore, the cost of a transaction's proposal, data publication, and verification at time $i$ is, denominated in the fee asset:
$$
\text{fee asset}_{tx} = \text{mana}_{tx} * \text{base wei per mana} * \text{fee asset per wei}
$$

## Distribution of the fee asset

When a transaction is included in a block in the pending chain, the L2 balance of the fee asset for the `fee_payer` of the transaction is reduced by the transactions's fee asset cost.

When an epoch is proven, the fees for the epoch are paid out to each proposer for the block(s) they proposed.

A fixed percentage of each block's fee asset fees are paid to the prover of the epoch. The percentage is determined based on the quote submitted by the prover for the epoch.

This quote is submitted by the prover in epoch `i+1` to prove epoch `i`, and is thus claimed/submitted to L1 by a proposer in epoch `i+1`.

In order to prevent a prover bribing a proposer into accepting a quote with an extremely high fee, the maximum fee a prover can submit for an epoch proof quote is `maximum_epoch_proof_quote_fee`.

## Clarifications and considerations

### Why is `blobs_per_block` a constant?

It makes computation easier. Otherwise block builder would need to know the number of blobs consumed by the transaction while it is building.

### L1 Congestion

If L1 gas spikes during an epoch, this will be reflected in the TST cost of a transaction through factoring in the higher `wei_per_l1_gas` and `wei_per_l1_blob_gas` into the TST cost.

However, the base fee is computed at the time of a block being proposed, based on the current L1 base fees. These may change between the block being proposed and the epoch being verified.

Thus, it is possible for L1 gas prices to spike to a point where it is not profitable for a prover to submit their proof to L1. There are two retorts:
1. The prover should bake in a risk premium to compensate them for this risk; it is similar to the risk that the price of TST relative to any other asset shifts against them.
2. The prover can wait until the end of the epoch waiting for a less congested window to submit their proof to L1.

### Not charging for DA separately

Current thinking is that proving costs will dominate the cost of a transaction, so metering DA is not necessary.

It also simplifies the implementation.

Regardless, the AVM supports DA gas metering per opcode, so it would not be difficult to add in the future if we change our mind.

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
