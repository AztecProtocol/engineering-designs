
# Template

|                      |                                            |
| -------------------- | ------------------------------------------ |
| Issue                | [title](github.com/link/to/issue)          |
| Owners               | @LHerskind @MirandaWood                    |
| Approvers            | @just-mitch @PhilWindle @iAmMichaelConnor  |
| Target Approval Date | YYYY-MM-DD                                 |


## Executive Summary

We will retire calldata for block bodies and instead use EIP-4844 blobs.

## Introduction

> Briefly describe the problem the work solves, and for whom. Include any relevant background information and the goals (and non-goals) of this implementation.

### Background

#### Our system 101
In our current system, we have an `AvailabilityOracle` contract.
This contract is relatively simple, given a bunch of transactions it will compute a commitment to them, by building a merkle tree from their transaction effects.
The root of this tree is then stored in the contract such that we can later check for availability.

When a block is proposed to the rollup contract, it will perform a query to the `AvailabilityOracle` to check availability of the `txs_effects_hash` of the header.

Since the only way it could be marked as available was by it being hashed at the oracle, we are sure that the data was published.

When the proof is to be verified, the `txs_effects_hash` is provided as a public input.
The circuits are proving that the "opening" of the commitment is indeed the transactions effects from the transactions of the block.

We are using just the hash for the public input instead of the transactions effects directly since it is a cost optimisation.
An extra public input have a higher cost than the extra layer of hashing that we need to do on both L1 and L2.
As the hashing are done both places, we use the `sha256` hash as it is relatively cheap on both sides.

It is a simple system, but using calldata and building the merkle tree on L1 is **very** gas intensive. 

#### What the hell is a blob?

- https://eips.ethereum.org/EIPS/eip-4844

Following 4844 (blob transactions), an Ethereum transaction can have up to 6 "sidecars" of 4096 field elements.
These sidecars are called blobs, and are by themselves NOT accessible from the EVM. 
However, a `VersionedHash` is exposed to the EVM, this is a hash of the version number and the kzg commitment to the sidecar.

```python
def kzg_to_versioned_hash(commitment: KZGCommitment) -> VersionedHash:
    return VERSIONED_HASH_VERSION_KZG + sha256(commitment)[1:]
```

If a `VersionedHash` is exposed to the EVM, the Ethereum network guarantees that the data (its 4096 fields) are published.

> @MirandaWood note:
> The `VersionedHash` (or `blobhash`) is available in the EVM once a blob has been published via a tx. For example, from [blob-lib](https://github.com/iAmMichaelConnor/blob-lib/blob/2a38f1022e6e1ee8d216d937f4ec2483aa5461b3/contracts/src/Blob.sol#L21-L35):
>```solidity
>    function submitBlobs() external {
>        bytes32 blobHash;
>        assembly {
>            blobHash := blobhash(0)
>        }
>        blobHashes[txId][0] = blobHash;
>        ++txId;
>    }
>```
> Like our `txs_effect_hash`, we must prove that the `blobhash` corresponds to the data in a published Aztec block (see [implementation section](#implementation)).

As you might have noticed, the `VersionedHash` and our `AvailabilityOracle` have a very similar purpose, if commitment is published according to it, then the pre-image of the commitment have also been published.

> Special Trivia for @iAmMichaelConnor:   
> The `to` field of a blob transactions cannot be `address(0)` so it cannot be a "create" transaction, meaning that your "fresh rollup contract every block" dream have a few extra hiccups. 
>Could still happen through a factory, but a factory make a single known contract the deployer and kinda destroy the idea.


### Goal 

Update the system to publish the transactions effects using blobs instead of calldata.

### Non-Goals

We do NOT change the data that is published, e.g., we will be publishing the transactions effects.

## Interface

Who are your users, and how do they interact with this? What is the top-level interface?

## Implementation

### Background

Essentially, we aim to replace publishing all a tx's effects in calldata with publishing in a blob. As mentioned above, any data inside a blob is *not available* to the EVM so we cannot simply hash the same data on L1 and in the rollup circuits, and check the hash matches, as we do now.

Instead, publishing a blob makes the `blobhash` available:

```solidity
/**
* blobhash(i) returns the versioned_hash of the i-th blob associated with _this_ transaction.
* bytes[0:1]: 0x01
* bytes[1:32]: the last 31 bytes of the sha256 hash of the kzg commitment C.
*/
bytes32 blobHash;
assembly {
    blobHash := blobhash(0)
}
```

Where the commitment $C$ is a KZG commitment to the data inside the blob over the BLS12-381 curve. There are more details [here](https://notes.ethereum.org/@vbuterin/proto_danksharding_faq#What-format-is-blob-data-in-and-how-is-it-committed-to) on exactly what this is, but briefly, given a set of 4096 data points inside a blob, $d_i$, we define the polynomial $p$ as:

$$p(\omega^i) = d_i.$$

In the background, this polynomial is found by interpolating the $d_i$ s (evaluations) against the $\omega^i$ s (points), where $\omega^{4096} = 1$ (i.e. is a 4096th root of unity).

This means our blob data $d_i$ is actually the polynomial $p$ given in evaluation form. Working in evaluation form, particularly when the polynomial is evaluated at roots of unity, gives us a [host of benefits](https://dankradfeist.de/ethereum/2021/06/18/pcs-multiproofs.html#evaluation-form). One of those is that we can commit to the polynomial (using a precomputed trusted setup for secret $s$ and BLS12-381 generator $G_1$) with a simple linear combination:

$$ C = p(s)G_1 = p(sG_1) = \sum_{i = 0}^{4095} d_i l_i(sG_1),$$

where $l_i(x)$ are the [Lagrange polynomials](https://dankradfeist.de/ethereum/2021/06/18/pcs-multiproofs.html#lagrange-polynomials). The details for us are not important - the important part is that we can commit to our blob by simply multiplying each data point by the corresponding element of the Lagrange-basis trusted setup (which is readily available in a few libraries) and summing the result!

### Proving DA

So to prove that we are publishing the correct tx effects, we just do this sum in the circuit, and check the final output is the same $C$ given by the EVM, right? Wrong. The commitment is over BLS12-381, so we would be calculating hefty wrong-field elliptic curve operations.

Thankfully, there is a more efficient way, already implemented by @iAmMichaelConnor in the [`blob-lib`](https://github.com/iAmMichaelConnor/blob-lib) repo and [`blob`](https://github.com/AztecProtocol/aztec-packages/tree/master/noir-projects/noir-protocol-circuits/crates/blob) crate in aztec-packages.

Our goal is to efficiently show that our tx effects accumulated in the rollup circuits are the same $d_i$ s in the blob committed to by $C$ on L1. To do this, we can provide an *opening proof* for $C$. In the circuit, we evaluate the polynomial at a challenge value $z$ and return the result: $p(z) = y$. We then construct a [KZG proof](https://dankradfeist.de/ethereum/2020/06/16/kate-polynomial-commitments.html#kate-proofs) in typescript of this opening (which is actually a commitment to the the quotient polynomial $q(x)$), and verify it on L1 using the [point evaluation precompile](https://eips.ethereum.org/EIPS/eip-4844#point-evaluation-precompile) added as part of EIP-4844. It has inputs:

- `versioned_hash`: The `blobhash` for this $C$
- `z`: The challenge value
- `y`: The claimed evaluation value at `z`
- `commitment`: The commitment $C$
- `proof`: The KZG proof of opening

It checks:

- `assert kzg_to_versioned_hash(commitment) == versioned_hash`
- `assert verify_kzg_proof(commitment, z, y, proof)`

As long as we use our tx effect fields as the $d_i$ values inside the circuit, and use the same $y$ and $z$ in the public inputs of the Honk L1 verification as input to the precompile, we have shown that $C$ indeed commits to our data. Note: I'm glossing over some details here which are explained in the links above (particularly the 'KZG Proof' and 'host of benefits' links).

But isn't evaluating $p(z)$ in the circuit also a bunch of very slow wrong-field arithmetic? No! Well, yes, but not as much as you'd think!

To evaluate $p$ in evalulation form at some value not in its domain (i.e. not one of the $\omega^i$ s), we use the [barycentric formula](https://dankradfeist.de/ethereum/2021/06/18/pcs-multiproofs.html#evaluating-a-polynomial-in-evaluation-form-on-a-point-outside-the-domain):

$$p(z) = A(z)\sum_{i=0}^{4095} \frac{d_i}{A'(\omega^i)} \frac{1}{z - \omega^i}.$$

What's $A(x)$, you ask? Doesn't matter! One of the nice properties we get by defining $p$ as an interpolation over the roots of unity, is that the above formula is simplified to:

$$p(z) = \frac{z^{4096} - 1}{4096} \sum_{i=0}^{4095} \frac{d_i\omega^i}{z - \omega^i}.$$

We can precompute all the $\omega^i$, $-\omega^i$ s and $4096^{-1}$, the $d_i$ s are our tx effects, and $z$ is the challenge point (discussed more below). This means computing $p(z)$ is threoretically 4096 wrong-field multiplications and 4096 wrong-field divisions, far fewer than would be required for BLS12-381 elliptic curve operations.

### Rollup Circuits

#### Base

Previously, the base rollup would `sha256` hash all the tx effects to one value and pass it up through the remaining rollup circuits. It would then be recalculated on L1 as part of the `AvailabilityOracle`.

We no longer need to do this, but we do need to pass up *something* encompassing the tx effects to the rollup circuits, so they can be used as $d_i$ s when we prove the blob opening. The simplest option would be to `poseidon2` hash the tx effects instead and pass those up, but that has some issues:

- If we have one hash per base rollup (i.e. per tx), we have an ever increasing list of hashes to manage.
- If we hash these in pairs, as we do now with the `tx_effects_hash`, then we need to recreate the rollup structure when we prove the blob.

The latter is doable, but means encoding some maximum number of txs, `N`, to loop over and potentially wasting gates for blocks with fewer than `N` txs. For instance, if we chose `N = 96`, a block with only 2 txs would still have to loop 96 times. 

Alvaro suggested a solution to this in the vein of `PartialStateReference`, where we provide a `start` and `end` state in each base and subsequent merge rollup circuits check that they follow on from one another. The base circuits themselves simply prove that adding the data of its tx indeed moves the state from `start` to `end`.

To encompass all the tx effects, we use a `poseidon2` sponge and absorb each field. We also track the number of fields added to ensure we don't overflow the blob (4096 BLS fields, which *can* fit 4112 BN254 fields, but adding the mapping between these is a TODO). Given that this struct is a sponge used for a blob, I have named it:

```rs
// Init is given by input len * 2^64 (see noir/noir-repo/noir_stdlib/src/hash/poseidon2.nr -> hash_internal)
global IV: Field = (FIELDS_PER_BLOB as Field) * 18446744073709551616;

struct SpongeBlob {
    sponge: Poseidon2,
    fields: u32,
}

impl SpongeBlob {
    fn new() -> Self {
        Self {
            sponge: Poseidon2::new(IV),
            fields: 0,
        }
    }
    // Add fields to the sponge
    fn absorb<let N: u32>(&mut self, input: [Field; N], in_len: u32) {
        // in_len is all non-0 input
        let mut should_add = true;
        for i in 0..input.len() {
            should_add &= i != in_len;
            if should_add {
                self.sponge.absorb(input[i]);
            }
        }
        self.fields += in_len;
    }
    // Finalise the sponge and output poseidon2 hash of all fields absorbed
    fn squeeze(&mut self) -> Field {
        self.sponge.squeeze()
    }
}
```

To summarise: each base circuit starts with a `start` `SpongeBlob` instance, which is either blank or from the preceding circuit, then calls `.absorb()` with the tx effects as input. Just like the output `BaseOrMergeRollupPublicInputs` has a `start` and `end` `PartialStateReference`, it will also have a `start` and `end` `SpongeBlob`.

Since we are removing a very large `sha256` hash, this should considerably lower gate counts for base.

#### Merge

We will no longer have two `tx_effect_hash`es from a merge circuit's `left` and `right` inputs to hash together, instead we have a `start` and `end` `SpongeBlob` and simply check that the `left`'s `end` `SpongeBlob` == the `right`'s `start` `SpongeBlob`.

We are removing one `sha256` hash and introducing a few equality gates, so gate counts for merge should be slightly lower.

#### Block Root

There have been multiple designs and discussions on where exactly the 'blob circuit', which computes $p(z) = y$, should live. See [this doc](https://hackmd.io/x0s4f3oTQa-K8IwPLGhqHA) for a write-up and [this board](https://miro.com/app/board/uXjVK4BC8Yg=/) for some diagrams.

The current route is option 5a in the document; to inline the blob functionality inside the block root circuit. We would allow up to 3 blobs to be proven in one block root rollup. For simplicity, the below explanation will just summarise what happens for a single blob.

First, we must gather all our tx effects ($d_i$ s). These will be injected as private inputs to the circuit and checked against the `SpongeBlob`s from the pair of `BaseOrMergeRollupPublicInputs` that we know contain all the effects in the block's txs. Like the merge circuit, the block root checks that the `left`'s `end` `SpongeBlob` == the `right`'s `start` `SpongeBlob`.

It then calls `squeeze()` on the `right`'s `end` `SpongeBlob` to produce the hash of all effects that will be in the blob. Let's call this `h`. The raw injected tx effects are `poseidon2` hashed and we check that the result matches `h`. We now have our set of $d_i$ s.

We now need to produce a challenge point `z`. This value must encompass the two 'commitments' used to represent the blob data: $C$ and `h` (see [here](https://notes.ethereum.org/@vbuterin/proto_danksharding_faq#Moderate-approach-works-with-any-ZK-SNARK) for more on the method). We simply provide $C$ as a public input to the block root circuit, and compute `z = poseidon2(h, C)`.

The block root now has all the inputs required to call the blob functionality. It is already written [here](https://github.com/AztecProtocol/aztec-packages/blob/f3e4f9734406eb58c52511b550cb99bdf28b13ea/noir-projects/noir-protocol-circuits/crates/blob/src/main.nr#L245), the only current difference being that we provide `z` rather than calculate it.

Along with the usual `BlockRootOrBlockMergePublicInputs`, we would also have $C$, $z$, and $y$. Of course, in reality all these values will be hashed to a single public input and reconstructed on L1, I've just omitted this detail for simplicity.

### L1 Contracts

> @MirandaWood note: This section is in the early design stages and needs more input. See TODOs at the bottom.

#### AvailabilityOracle

We are replacing publishing effects with `AvailabilityOracle.sol` with instead publishing a blob. A high level overview of this change is to provide the blob as the `data` part of the tx calling `propose()` instead of calling `AvailabilityOracle.publish()`.

This does not mean actually sending the data to the EVM - this only makes the `blobhash` available. The function `propose()` should then extract and store this `blobhash` alongside the `blockHash` for future verification.

#### Rollup

As mentioned, we now have new public inputs to use for verifying the blob. As usual, `submitBlockRootProof` verifies the Honk proof against its `BlockRootOrBlockMergePublicInputs` and performs checks on them. With the addition of the blobs, we now must also input and check the KZG opening proof. Note that the below pseudocode is just an overview, as the precompile actually takes `bytes` we must encode:

```solidity
        // input for the blob precompile
        bytes32[] input;
        // extract the blobhash from the one submitted earlier:
        input[0] = blobHashes[blockHash];
        // z, y, and C are already used as part of the PIs for the block root proof
        input[1] = z;
        input[2] = y;
        input[3] = C;
        // the opening proof is computed in ts and inserted here
        input[4] = kzgProof;

        // Staticcall the point eval precompile https://eips.ethereum.org/EIPS/eip-4844#point-evaluation-precompile :
        (bool success, bytes memory data) = address(0x0a).staticcall(input);
        require(success, "Point evaluation precompile failed");
```

I'm also glossing over the fact that we are allowing each block to have up to 3 blobs, so we would need to ensure that the 3 KZG opening proofs and blobhashes are handled properly.

Note that we do not need to check that our $C$ matches the `blobhash` - the precompile does this for us.

### Typescript

> @MirandaWood note: This section is in the early design stages and needs more input. See TODOs at the bottom.

We would require:

 - Updates to contructing circuit inputs, such that each base is aware of the 'current' `SpongeBlob` state, like we already do with `PartialStateReference`s, and raw tx effects are injected to the private inputs of block root.
 - Adding functionality to tx sending code to:
    - Construct and include blobs when sending `propose` txs to L1.
    - Use the [`c-kzg`](https://www.npmjs.com/package/c-kzg) package to calculate the KZG opening proof (and other information for checks) - example usage in the `blob-lib` [here](https://github.com/iAmMichaelConnor/blob-lib/blob/main/src/blob-submission.test.ts).
- Include new structs and tests corresponding to rollup circuit updates.
- Add functionality to read blob information from L1.

### TODOs/Considerations

#### Batch rollups

All the above assumes verifying a final block root proof on L1, when we will actually be verifying a root proof, encompassing many blocks and therefore many more blobs per verification. I'm not sure entirely how managing the L1 state will look for this change and how best to align this with storing the information required to verify the blob via the KZG proof.

#### Gas

Whether verifying block root or root proofs on L1, a single call performing a Honk verification and up to 3 calls to the KZG point evaluation precompile may be too costly. It's possible to store $C$, $z$, and $y$ against the `blockHash` for a separate call to the precompile, but we have to consider that DA is not 'confirmed' until this call has happened.

#### Tx Objects

Since all the blob circuit code above 'cares' about is an array of fields matching another array of fields, it should theoretically not affect too much. However we should be careful to include all the new effects in the right structure to be read by clients from L1.

#### Other

>@MirandaWood note: I'm sure there are plenty of areas I'm not familiar in which would be affected by this. Hopefully this doc gives a decent overview of the rollup circuit changes and a bit of the maths behind blobs.


## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [x] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [x] Rollup Circuits
- [x] L1 Contracts
- [x] Archiver
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.


### Solidity

Forge does allow emitting a blob, however, it allows for mocking a set of KZG hashes, 

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
