|                      |                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------- |
| Owners               | @PhilWindle                                                                                   |
| Approvers            | @just-mitch @alexghr                                                                          |
| Target Approval Date | 2024-06-21                                                                                    |


## Executive Summary

This design attempts to solve the problem of slow sync and merkle tree insertion performance.


## Introduction

We require high performance merkle tree implementations both to ensure nodes can stay synсhed to the network and sequencers/provers can advance the state as required to build blocks. Our current TS implementations are limited in their single-threaded nature and the unavoidable constraint of have to repeatedly call into WASM to perform a hash operation.

Some analysis of the quantity of hashing and the time required can be found [here](https://hackmd.io/@aztec-network/HyfTK9U5a?type=view).

This design proposes the creation of a set of multi-threaded merkle tree implementations in C++ using LMDB. It builds upon some previous prototyping to develop concurrent indexed tree insertions.

## Implementation

There are many parts to this design, we will walk through them individually and discuss the choices made at each stage.

### Overall Architecture

A new C++ binary, World State, will be created that will be started by the node software. It will be configured with the location in which Merkle Tree data should be stored. It will then accept and respond with msgpack-ed messages over one or more streams. The initial implementation will simply used stdio, but this will be abstracted such that this could be replaced by other stream-based mechanisms.

To interface with the World State, an abstraction will be created at the `MerkleTreeDb` level. This accurately models the scope of functionality provided by the binary as owner of all the trees. It was considered that the abstraction could sit at the level of individual trees, but this creates difficulty when we want to send an entire block to the World State to be inserted. This is an important use case as synching entire blocks is where significant performance optimisations can be made.


``` TS
export type MerkleTreeDb = {
  [Property in keyof MerkleTreeOperations as Exclude<Property, MerkleTreeSetters>]: WithIncludeUncommitted<
    MerkleTreeOperations[Property]
  >;
} & Pick<MerkleTreeOperations, MerkleTreeSetters> & {
    /**
     * Returns a snapshot of the current state of the trees.
     * @param block - The block number to take the snapshot at.
     */
    getSnapshot(block: number): Promise<TreeSnapshots>;
  };
```

An abstract factory will then be created to construct the appropriate concrete type based on whether an instance of the node has native World State or not.

### Interface

The interface will be an asynchronous message based communication protocol. Each message is provided with meta data uniquely identifying it and is responded to individually. It is not necessary to wait for a response to a message before sending a subsequent message. A simple message specification will be created, some examples of which are shown here:

``` C++
enum WorldStateMsgTypes {
    START_TREE_REQUEST = FIRST_APP_MSG_TYPE,
    START_TREE_RESPONSE,
    GET_TREE_INFO_REQUEST,
    GET_TREE_INFO_RESPONSE,
    INSERT_LEAVES_REQUEST,
    INSERT_LEAVES_RESPONSE,
};

struct MsgHeader {
    uint32_t messageId; // Unique Id for the message
    uint32_t requestId; // Id of the message this is responding to (may not be used)

    MSGPACK_FIELDS(messageId, requestId);

    MsgHeader() = default;

    MsgHeader(uint32_t reqId)
        : requestId(reqId)
    {}

    MsgHeader(uint32_t msgId, uint32_t reqId)
        : messageId(msgId)
        , requestId(reqId)
    {}
};

struct GetTreeInfoRequest {
    std::string name;

    MSGPACK_FIELDS(name);
};

struct GetTreeInfoResponse {
    std::string name;
    uint32_t depth;
    bb::fr root;
    uint64_t size;
    bool success;
    std::string message;

    MSGPACK_FIELDS(name, depth, root, size, success, message);
};

template <class T> struct TypedMessage {
    uint32_t msgType;
    MsgHeader header;
    T value;

    TypedMessage(uint32_t type, MsgHeader& hdr, const T& val)
        : msgType(type)
        , header(hdr)
        , value(val)
    {}

    TypedMessage() = default;

    MSGPACK_FIELDS(msgType, header, value);
};
```

``` TS
export type GetTreeInfoRequest = {
  name: string;
}

export type GetTreeInfoResponse = {
  name: string;
  depth: number;
  success: boolean;
  message: string;
  root: Buffer;
  size: bigint;
}
```

### LMDB

LMDB is a high performance key-value database allowing for concurrent read/write access and fully ACID transactions. In particular, it supports up to 126 concurrent read transactions. Write transactions can be performed concurrently with reads but we won't use this. The majority of our World State operations only require read access to persisted data.

There are 3 broad categories of World State operations:

#### Reads

Simply reading data from the trees is performed using either `committed` or `uncommitted` state. Committed state is that which has fully settled and is therefore not going to change over the course of building a block. It can only change upon settlement of a new block. Uncommitted reads will read from the pending state, it is not recommended that uncommitted reads are performed by anyone other than a sequencer/prover.

Examples of reads are requesting sibling paths, state roots etc.

#### Updates

As a sequencer/prover inserts transaction side-effects, the resulting new state is computed and cached in memory. This allows for the separation of `committed` and `uncommitted` reads and the easy rolling back of unsuccessful blocks.

#### Commits

When a block settles, the node performs a commit. It verifies any uncommitted state it may have against that published on chain to determine if that state is canonical. If it is not, the `uncommitted` state is discarded and the node perform an `Update` operation using the newly published side effects.

Once the node has the correct `uncommitted` state, it commits that state to disk. This is the only time that a write transaction is required against the database.

### Updating the World State

The `Update` operation involves inserting side-effects into one or more trees. Depending on the type of tree, we can make significant optimisations to reduce the real-world time taken.

#### Append Only

Append only trees don't support the updating of any leaves. New leaves are inserted at the right-most location and nodes above these are updated to reflect their newly hashed values. Optimisation here is simply a case of dividing the set of leaves into smaller batches and hashing each of these batches into a sub-tree in separate threads. Finally, the roots are used to build the sub-tree on top before hashing to the root of the main tree.

#### Indexed Tree

Indexed Trees require significantly more hashing than append only trees. In fact, adding a set of leaves to an Indexed Tree finishes with an append only tree insertion of the new leaves. However, before this, it is necessary to update all 'low-value' leaves first.

For each leaf being inserted:

1. Identify the location of the leaf whose value immediately precedes that being inserted.
2. Retrieve the sibling path of the preceding leaf before any modification.
3. Set the 'next' value and index to point to the leaf being inserted.
4. Set the 'next' value and index of the leaf being inserted to the leaf previously pointed to by the leaf just updated.
5. Re-hash the updated leaf and update the leaf with this hash, requiring the tree to be re-hashed up to the root.

Unfortunately, this process is very sequential with minimal opportunity for concurrent hashing. Each sibling path must be taken after having updated the 'low leaf' for the previous insertion. We can achieve a reasonable degree of concurrency here though. We first identify all of the 'low-leaf' values that need updating, then for each we merge steps 2 and 5, making a single pass up the tree, retrieving each node's value before overwriting it. We can then schedule each of these tree traversals as a unit of work to be carried out on a thread pool.

For example, we have a depth 3 Indexed Tree and 2 leaves to insert. The first requires leaf at index 0 to be updated, the second requires leaf at index 1 to be updated. 

1. Thread 1 reads the current leaf at level 2 (the leaf level), index 0 to populate it's sibling path, then writes the new leaf value.
2. Thread 1 reads the sibling at level 2, index 1, writes the new hash into level 1, index 0 (the parent node).
3. Thread 1 signals that it has finished with level 2.
4. Thread 2, having waited for the signal to indicate level 2 is clear can now start it's traversal of the tree, performing the same procedure.

In the above example, Thread 2 will follow Thread 1 up the tree, providing a degree of concurrency to the update operation. Obviously, this example if limited, in a 40 depth tree it is possible to have many threads working concurrently to build the new state without collision.

In this concurrent model, each thread would use its own single read transaction to retrieve `committed` state and all new `uncommitted` state is written to the cache in a lock free manner as every thread is writing to a different level of the tree.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] L1 Contracts
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] Aztec.nr
- [ ] Noir
- [ ] AVM
- [x] Sequencer
- [ ] Fees
- [ ] P2P Network
- [ ] Cryptography
- [ ] DevOps

## Test Plan

As the World State is used heavily in all operations, we will gain confidence through the use of:

1. Unit tests within the C++ section of the repo.
2. Further sets of unit tests in TS, comparing the output of the native trees to that of the TS trees.
3. All end to end tests will inherently test the operation of the World State.

## Prototypes

Areas of this work have been prototyped already. The latest being [here](https://github.com/AztecProtocol/aztec-packages/pull/7037).
