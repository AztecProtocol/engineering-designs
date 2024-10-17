# Testnet Fees

|                      |                                                                               |
| -------------------- | ----------------------------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8757                   |
| Owners               | @just-mitch                                                                   |
| Approvers            | @LHerskind @Maddiaa0 @PhilWindle @dbanks12 @nventuro @joeandrews @aminsammara |
| Target Approval Date | 2024-10-24                                                                    |

## Costs

Suppose a user pays fees in a test token TST.

Refer to the unit of work on L2 as "mana", analogous to gas on L1.

A transaction incurs the following costs:
1. Proposers/validators simulate the transaction
2. Proposers publish pending blocks to L1
3. Provers generate the avm proofs for the transaction
4. Provers generate the rollup proofs for the blocks/epoch
5. Provers verify the epoch proof on L1

Some costs are independent of the computation or data of the transaction itself, specifically numbers 2, 4, and 5; regardless, they must be covered by the transaction.

## Revenues

Suppose we have the following parameters:
- `target_transactions_per_second` - the number of transactions per second that the rollup is designed to handle
- `seconds_per_l2_slot` - the number of seconds in each L2 slot
- `l2_slots_per_l2_epoch` - the number of L2 slots in each L2 epoch
- `l1_gas_per_block_proposed` - the amount of gas required to propose an L2 block on L1
- `l1_gas_per_epoch_verified` - the amount of gas required to verify an L2 epoch on L1


We can establish fixed costs for a transaction in L1 gas for *proposal*:
$$
\text{Proposal L1 gas per transaction} = \frac{\text{L1 gas per block proposed}}{\text{target transactions per second} * \text{seconds per L2 slot}}
$$

And for *verification*:
$$
\text{Verification L1 gas per transaction} = \frac{\text{L1 gas per epoch verified}}{\text{target transactions per second} * \text{seconds per L2 slot} * \text{L2 slots per L2 epoch}}
$$

So we can establish the total *Fixed* cost of a transaction in L1 gas:

$$
\text{gas}_{tx} = \text{Proposal L1 gas per transaction} + \text{Verification L1 gas per transaction}
$$

A particular transaction has a variable cost in L1 blob gas which is consumed when it is proposed.

$$
\text{blob gas}_{tx} = \text{32 blob gas per field} * \text{number of fields in the transaction's published data}
$$

Therefore, the cost of a transaction's proposal, data publication, and verification at time $i$ is, denominated in eth:
$$
\text{eth}_{tx,i} = \text{blob gas}_{tx} * \text{eth per blob gas}_i + \text{gas}_{tx} * \text{eth per gas}_i
$$

Where the eth per blob gas and eth per gas are the `base_fee`s of these resources on L1 at time `i`.

Assume the existence of an "oracle" which provides the `mana_per_eth` rate (more on this below) at any time `i`. The cost of a transaction's L1 interactions in mana is then:
$$
\text{mana}_{tx,L1,i} = \text{eth}_{tx,i} * \text{mana per eth}_{i}
$$

Last, assume the existence of an "oracle" which provides the `tst_per_mana` rate, analogous to the `eth_per_gas` rate on L1.

The cost of a transaction's L1 interactions in TST is then:
$$
\text{TST}_{tx,L1,i} = \text{mana}_{tx,L1,i} * \text{tst per mana}_{i}
$$

What remains is to establish the cost of the transaction's L2/prover interactions. The cost of a transaction's L2 interactions in mana is:
- Simulating the transaction
- Generating the AVM/Public kernel proofs
- Generating the rollup proofs

Generating the rollup proof is a fixed cost, and independent of the transaction's data, but rather on the number of transactions on a block, and the number of slots in an epoch, which we have established targets for. Thus we can establish a fixed, base cost in `mana` for transactions as $\text{mana}_{tx,base}$.

Every operation that a transaction performs in its public execution will have a cost in `mana`. The cost of a transaction's L2 interactions in `mana` is then:

$$
\text{mana}_{tx,L2} = \text{mana}_{tx,base} + \sum_{op \in tx} \text{mana per operation}(op)
$$

The cost of a transaction's L2 interactions in TST is then:

$$
\text{TST}_{tx,L2,i} = \text{mana}_{tx,L2} * \text{tst per mana}_{i}
$$


The total cost of a transaction `tx` in TST at time `i` is then:

$$
\text{TST}_{tx,i} = \text{TST}_{tx,L1,i} + \text{TST}_{tx,L2,i}
$$


### `mana_per_eth` oracle

As mentioned, an oracle is needed to convert the cost of a transaction's L1 interactions in eth to mana.

This will be stored on the rollup contract. On proposing a block, proposers will be able to adjust the rate by up to a predefined percentage. 

### `tst_per_mana` oracle

We borrow from EIP-1559. The `tst_per_mana` rate will be stored on the rollup contract. We will establish the following parameters on the rollup contract:
- `target_mana_per_block` - the target amount of mana that a block should consume
- `limit_mana_per_block` - the maximum amount of mana that a block can consume

The target/limit mana will only be accounting for mana consumed in the L2 execution for a proposed block, i.e. $\sum_{tx \in \text{block}} mana_{tx,L2}$.

In order to drive this oracle, the L2 block header must contain a `total_l2_mana_consumed` field in addition to the existing `total_fees` field.

## Distribution

When a transaction is included in a block in the pending chain, the L2 balance of TST for the `fee_payer` of the transaction is reduced by the transactions's TST cost.

When an epoch is proven, the fees for the epoch are paid out to each proposer for the block(s) they proposed.

A fixed percentage of each block's TST fees are paid to the prover of the epoch. The percentage is determined based on the quote submitted by the prover for the epoch.

This quote is submitted by the prover in epoch `i+1` to prove epoch `i`, and is thus claimed/submitted to L1 by a proposer in epoch `i+1`.

In order to prevent a prover bribing a proposer into accepting a quote with an extremely high fee, proposers in epoch `i` will be able to submit a maximum fee they are willing to accept for the quote to be accepted in epoch `i+1`.

The maximum fee will then be averaged throughout the epoch, and the quote claimed in epoch `i+1` must have a fee less than or equal to this average.

## L1 Congestion

If L1 gas spikes during an epoch, this will be reflected in the TST cost of a transaction through:

$$
\begin{aligned}
\text{eth}_{tx,i} &= \text{blob gas}_{tx} * \text{eth per blob gas}_i + \text{gas}_{tx} * \text{eth per gas}_i \\
\text{mana}_{tx,L1,i} &= \text{eth}_{tx,i} * \text{mana per eth}_{i}
\end{aligned}
$$

Note that "$\text{mana per eth}_i$" does not need to change to reflect this.

Also, this compensates for spikes in blob gas prices.

However, it is possible for L1 gas prices to spike to a point where it is not profitable for a prover to submit their proof to L1. There are two retorts:
1. The prover should bake in a risk premium to compensate them for this risk; it is similar to the risk that the price of TST relative to any other asset shifts against them.
2. The prover can wait until the end of the epoch waiting for a less congested window to submit their proof to L1.

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
- [ ] L1 Contracts
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
