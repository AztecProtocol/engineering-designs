# Incentives

|                      |                                                             |
| -------------------- | ----------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8757 |
| Owners               |                                                             |
| Approvers            |                                                             |
| Target Approval Date | YYYY-MM-DD                                                  |


## Costs

A user pays fees in a token TST.

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
\text{eth}_{tx,i} = \text{blob gas}_{tx} * \text{eth per blob gas at time i} + \text{gas}_{tx} * \text{eth per gas at time i}
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

## Distribution

When a transaction is included in a block in the pending chain, the L2 balance of TST for the `fee_payer` of the transaction is reduced by the transactions's TST cost.

That cost was determined based on the the oracles' rates, which are held constant for a particular slot/block.

To maintain sound accounting, it must be ensured that:
- The TST is not paid out until the block is in the proven chain.
- The TST paid to a proposer is equal to the TST cost of the transactions in the block, borne by the proposer.

The second point can be ensured by keeping track in the rollup contract the TST due to a proposer for a block.

This is computed as:

$$
\text{Mana for L1 propose function} = \text{Number of transactions in block} \\ * \text{ Proposal L1 gas per transaction} \\ * \text{eth per gas}_i \\ * \text{mana per eth}_{i} 
\\
\text{blob mana} : ( transaction, time ) \to mana  := \text{blob gas}_{tx} \\ * \text{eth per blob gas}_{i} \\ * \text{mana per eth}_{i}
\\
\text{operation mana} : ( transaction ) \to mana := \sum_{op \in tx} \text{mana per operation}(op)
\\
\text{Mana for computation}(block, i) = \sum_{tx \in \text{block}}\lparen \text{blob mana}(tx, i) + \text{operation mana}(tx) + \text{base mana} \rparen
\\
\text{Mana for proposed block} = \text{Mana for L1 propose function} + \text{Mana for computation}(block, i)
$$



However, this fee is not paid out until the block is in the proven chain.

Further, to maintain sound accounting, we 


Part of the public inputs to the epoch proof is, for each block, the amount of TST collected and the ethereum address of the proposer.

Given a block's fees, the amount of TST paid to the proposer is:





## Introduction

## Interface

## Implementation

eth

```solidity
contract Rollup {

  
  uint256 public 
  uint256 public ethGasUsed;
  uint256 public daGasUsed;

  function 
}
```


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
