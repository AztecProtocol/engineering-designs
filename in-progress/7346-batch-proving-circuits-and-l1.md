|                      |                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| Issue                | [Batch proving in Circuits and L1](https://github.com/AztecProtocol/aztec3-packages/issues/7346) |
| Owners               | @spalladino                                                                                      |
| Approvers            | @LeilaWang @LHerskind @iAmMichaelConnor                                                          |
| Target Approval Date |                                                                                                  |

## Summary

With the separation of sequencers and provers, we now want to submit root rollup proofs that encompass multiple blocks. This requires changes in the rollup circuit topology as well as the L1 Rollup contract.

## Circuits

Let's first review the responsibilities of the current merge and root rollup circuits.

### Merge Rollup

The merge rollup circuit has the following inputs:

```rust
struct MergeRollupInputs {
  previous_rollup_data: [{
    public_inputs: BaseOrMergeRollupPublicInputs
    nested_proof: NestedProof,
  }; 2]
}
```

The circuit then performs the following checks and computations:

- Recursively verifies the left and right inputs
- Checks that the tree is greedily filled from left to right
- Checks that constants from left and right match
- Checks that the end state from left matches the start state from right (ie they follow from each other)
- Outputs the start of left and end of right
- Hashes together or sums up any accumulated fields (tx count, effects hashes, accumulated fees, etc)
- Propagates constants

And outputs:

```rust
struct BaseOrMergeRollupPublicInputs {
  constants: {
    previous_archive: TreeSnapshot,
    global_variables: { block_number, timestamp, ... }
  },
  start: PartialStateReference,
  end: PartialStateReference,
  txs_effects_hash: Field,
  out_hash: Field,
  accumulated_fees: Field
  num_txs: Field,
}
```

### Root rollup

The root rollup takes the same inputs as merge rollup, plus fields related to L1-to-L2 messaging, and related to updating the archive tree with the new block root.

```rust
struct RootRollupInputs {
    previous_rollup_data : [PreviousRollupData; 2],

    l1_to_l2_roots: RootRollupParityInput,
    l1_to_l2_messages : [Field; NUMBER_OF_L1_L2_MESSAGES_PER_ROLLUP],
    l1_to_l2_message_subtree_sibling_path : [Field; L1_TO_L2_MSG_SUBTREE_SIBLING_PATH_LENGTH],
    start_l1_to_l2_message_tree_snapshot : AppendOnlyTreeSnapshot,

    start_archive_snapshot : AppendOnlyTreeSnapshot,
    new_archive_sibling_path : [Field; ARCHIVE_HEIGHT],
}
```

It performs the same checks as the merge circuit, plus:

- Creates a new L1-to-L2 tree snapshot
- Creates the new block header, which includes the previous archive tree root
- Updates the archive tree with the new block hash

```rust
struct RootRollupPublicInputs {
    archive: AppendOnlyTreeSnapshot,
    header: {
      previous_archive: AppendOnlyTreeSnapshot,
      content_commitment: ContentCommitment,
      state: StateReference,
      global_variables: GlobalVariables,
      total_fees: Field
    }
}
```

### New rollup structure

We propose changing the current rollup structure introducing two new circuits, a **block root rollup** and a **block merge rollup** circuit. The block root rollup circuit acts exactly the same as today's root rollup, grouping multiple base rollup into a tree via merge rollups until it produces a block. The block merge rollup circuits would then merge multiple blocks into a tree, until it reaches a new root rollup that proves a block range.

The tree levels, from top to bottom, would then be:

- Root
- Block merge
- Block root
- Merge
- Base

### Block root rollup

The block root rollup circuit is the same as today's root rollup circuit, but with its public inputs tweaked so it matches the public inputs from the block merge rollup as well, in the same way as today the base rollup public inputs are tweaked so they match the ones from the merge rollup.

```rust
struct BlockRootOrBlockMergePublicInputs {
  previous_archive: AppendOnlyTreeSnapshot, // Archive tree root immediately before this block
  new_archive: AppendOnlyTreeSnapshot, // Archive tree root after adding this block
  previous_block_hash: Field, // Identifier of the previous block
  end_block_hash: Field, // Identifier of the current block
  out_hash: Field, // Merkle root of the L2-to-L1 messages in the block
  start_global_variables: GlobalVariables, // Global variables for this block
  end_global_variables: GlobalVariables, // Global variables for this block
  fees: [{ recipient: Address, value: Field }; 32], // Single element equal to global_variables.coinbase and total_fees for the block
}
```

### Block merge rollup

The block merge rollup circuit, following the same line of the merge circuit, would take two `BlockRootOrBlockMergePublicInputs` and merge them together:

```rust
struct BlockMergeInputs {
  previous_rollup_data: [{
    public_inputs: BlockRootOrBlockMergePublicInputs
    nested_proof: NestedProof,
  }; 2]
}
```

Note that the semantics of the `BlockRootOrBlockMergePublicInputs` are now generalized to a block range:

```rust
struct BlockRootOrBlockMergePublicInputs {
  previous_archive: AppendOnlyTreeSnapshot, // Archive tree root immediately before this block range
  new_archive: AppendOnlyTreeSnapshot, // Archive tree root after adding this block range
  out_hash: Field, // Merkle node of the L2-to-L1 messages merkle roots in the block range
  previous_block_hash: Field, // Identifier of the previous block before the range
  end_block_hash: Field, // Identifier of the last block in the range
  start_global_variables: GlobalVariables, // Global variables for the first block in the range
  end_global_variables: GlobalVariables, // Global variables for the last block in the range
  fees: [{ recipient: Address, value: Field }; 32] // Concatenation of all coinbase and fees for the block range
}
```

This circuit then performs the following checks and computations:

- Recursively verifies the left and right inputs
- Checks that `right.previous_archive` equals `left.new_archive`
- Checks that `right.previous_block_hash` equals `left.end_block_hash`
- Checks that `right.start_global_variables` follow from `left.end_global_variables`
- Concatenates and outputs the `fees` from both inputs
- Outputs `sha256(left.out_hash, right.out_hash)` as its own `out_hash`
- Outputs `previous_archive`, `start_global_variables`, and `previous_block_hash` from `left`
- Outputs `new_archive`, `end_global_variables`, and `end_block_hash` from `right`

Note that we say that the global variables in `right` "follow" the ones in `left` if:

- `left.chain_id == right.chain_id`
- `left.version == right.version`
- `left.block_number == right.block_number + 1`
- `left.timestamp < right.timestamp`
- `coinbase`, `fee_recipient`, and `gas_fees` are not constrained (though `gas_fees` may be in a 1559-like world)

### Root rollup

The new root rollup circuit then takes two `BlockRootOrBlockMergePublicInputs`, performs the same checks as the block merge rollup, but outputs a subset of the public inputs, to make L1 verification cheaper:

```rust
struct RootRollupPublicInputs {
  previous_archive: Field,
  end_archive: Field,
  end_block_hash: Field,
  end_timestamp: Field,
  end_block_number: Field,
  out_hash: Field,
  fees: [{ recipient: Address, value: Field }; 32]
}
```

### Empty block root rollup

Since we no longer submit a proof per block, and thanks to @MirandaWood we now have wonky rollups, we no longer need to fill a block with "empty" txs. This means we can discard the empty private kernel circuit.

However, we still need to be able to represent an empty block. We can do this by introducing an empty block root rollup circuit, which outputs a `BlockRootOrBlockMergePublicInputs` which does not consume any merge rollups, and the end state just equals the start state. Note that we may still need an empty nested circuit to fill in the nested proof.

## L1 Rollup Contract

The Rollup contract today has a main entrypoint `process(header, archive, aggregationObject, proof)`. We propose breaking this method into two:

```solidity
contract Rollup {
  process(header, archive);
  submitProof(publicInputs, aggregationObject, proof);
}
```

### State

To track both the proven and unproven chains, we add the following state variables to the contract:

```diff
contract Rollup {
  bytes32 lastArchiveTreeRoot;
  uint256 lastBlockTimestamp;
+ bytes32 verifiedArchiveTreeRoot;
+ uint256 verifiedBlockTimestamp;
}
```

The `last*` fields are updated every time a new block is uploaded, while the `verified*` ones are updated when a proof is uploaded. In the event of a rollback due to failure on proof submission, the `last*` fields are overwritten with the contents of `verified*`.

### Process

Today the `process` method does the following:

1. Validate the new block header
2. Update the `lastArchiveTreeRoot` and `lastBlockTimestamp` in the contract storage
3. Consume L1-to-L2 messages from the Inbox
4. Emit an `L2BlockProcessed` event with the block number
5. Test data availability against the availability oracle
6. Verify the root rollup proof
7. Insert L2-to-L1 messages into the Outbox using the `out_hash` and block number
8. Pay out `total_fees` to `coinbase` in the L1 gas token

The first four items can keep being carried out by the `process` method for each new block that gets submitted. Proof verification, L2-to-L1 messages, and fee payment messages are moved to `submitProof`. Data availability needs more clarity based the interaction between the blob circuits and the point evaluation precompile, but it may be moved entirely to `submitProof`.

As for consuming L1-to-L2 messages, note that these cannot be fully deleted from the Inbox, since we need to be able to rollback unproven blocks in the event of a missing proof, which requires being able to consume those messages again on the new chain.

Last, we should rename `process` to something more descriptive, such as `submitBlock`.

### Submit proof

This method receives the root rollup public inputs, plus the aggregation object and proof to verify. Its responsibilities are the ones removed from `process`:

1. Verify the root rollup proof
2. Insert L2-to-L1 messages into the Outbox using the `public_inputs.out_hash` and the _last block number in the range_
3. Pay out `value` to `recipient` in the L1 gas token for each pair in the `public_inputs.fees` array

In addition, this method:

1. Checks that the `public_inputs.previous_archive` matches the current `verifiedArchiveTreeRoot` in the L1 contract (ie that the block range proven follows immediately from the previous proven block range).
2. Proves that the `end_block_hash` is in the `lastArchiveTreeRoot` (ie that the last block in the range proven is actually part of the pending chain) via a Merkle membership proof.
3. Updates the `verifiedArchiveTreeRoot` and `verifiedBlockTimestamp` fields in the L1 contract.
4. Emits an `L2ProofVerified` event with the block number.

## Discussions

### Binary vs fixed-size block merge rollup circuit

Assuming we implement a proving coordination mechanism where the block ranges proven are of fixed size (eg 32), then we could have a single circuit that directly consumes the 32 block root rollup proofs and outputs the public inputs expected by L1. This could be more efficient than constructing a tree of block root rollup proofs. On the other hand, it is not parallelizable, inflexible if we wanted a dynamic block range size, and must wait until all block root rollup proofs are available to start proving.

### Batched vs optimistic vs pull fee payments

In the model above, fee payments are executed in-batch at the time the proof is submitted. Assuming the L1 payment token includes a `transferBatch` method, the cost of 32 payments can be brought down to about 160k gas (5000 x 32), which is manageable. However, it imposes a max size on the number of blocks it can be proven on a single batch, and 160k is still a significant number.

Alternatively, we could keep fee payments as part of the `Rollup.process` method, so that a sequencer is payed the moment they submit a block, even if it doesn't get proven. Depending on how we implement unhappy paths in block building, we could optimistically pay fees on submission, and recoup them as part of a slashing mechanism. This would also simplify the block rollup circuits, as we would not need to construct an array of payments. Either way, it could be a good idea to start with this approach initially as it requires the least engineering effort.

Another option is to implement pull payments via merkle proofs, where each proof submits not the explicit list of payments but a merkle root of them, which gets stored in the contract. Sequencers then need to submit a merkle membership proof to claim their corresponding fees. This gives us the flexibility of being able to cram as many blocks in a proof as we want to, but adds significant complexity and gas cost to sequencers.
