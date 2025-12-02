# Chain Finalization Names RFC

Request for comments on how to name the multiple tips of the chain based on their finalization status, especially considering the shift to building-in-chunks.

## Where we are today

We currently have three chain tips:

- `pending`: Latest L2 block posted to L1
- `proven`: Latest L2 block that received a proof on L1
- `finalized` Latest L2 block that is proven such that the proof is in a finalized L1 block

As we add building-in-chunks, we'll have a new tip which is a block that has been proposed and attested, but not yet submitted to L1 as part of a checkpoint. We've provisionally called this chain `provisional`.

## What we propose

- `proposed`: Latest block proposed by the current proposer and reexecuted locally.
  - Alternatives considered: `candidate`, `latest`, `provisional`
- `checkpointed`: Latest block included in an L1 checkpoint
  - Formerly `pending`, which is a bad name since it has a different meaning in Ethereum
  - Alternatives considered: `safe`, `committed`, `mined`
- `proven`: Latest block verified by a validity proof on L1
  - Alternatives considered: `verified`
- `finalized`: Latest block verified on a finalized L1 block
  - Same as before

## What other networks are doing

For reference, here are the conventions that other chains use.

### Ethereum

See [here](https://www.alchemy.com/overviews/ethereum-commitment-levels):

- `pending`: Refers to a potential upcoming block to be produced, eg txs in the mempool and not included in a block are said to be pending.
- `latest`: Last block produced and voted by the validator committee.
- `safe`: Synonym with justified, block has received attestations from two-thirds of Ethereum’s validator.
- `finalized`: Justified block that is 1 epoch behind the most recently justified block.

### Optimism

See [here](https://docs.optimism.io/concepts/transactions/transaction-finality):

- `unsafe`: Built by the sequencer but not yet published to L1
- `safe`: Published to L1
- `finalized`: Published to an L1 finalized block

### ZK Sync

See [here](https://docs.zksync.io/zksync-protocol/rollup/finality#finality-on-zksync-chains):

- _Batch Formation_: Transactions are collected and grouped into a batch. This step generally takes a few minutes.
- _Batch Commitment_: The complete batch is committed to the Ethereum blockchain.
- _Proof Generation_: A cryptographic proof that validates the entire batch is generated. This process typically takes about an hour.
- _Proof Submission_: The generated proof is submitted to an Ethereum smart contract for verification.
- _Batch Finalization_: The batch undergoes a final verification and is settled on Ethereum. This step includes a delay of approximately 3 hours as a security measure

### Starknet

See [here](https://docs.starknet.io/learn/protocol/transactions) for _tx_ lifecycle:

- `RECEIVED`: Received by a sequencer
- `CANDIDATE`: In the way to be executed
- `PRE_CONFIRMED`: Executed by the sequencer
- `ACCEPTED_ON_L2`: L2 consensus accepted the tx
- `ACCEPTED_ON_L1`: Submitedd to L1 (unclear if this is includes the proof)
