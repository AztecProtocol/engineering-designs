|                      |                                   |
| -------------------- | --------------------------------- |
| Issue                | [Blob integration](https://github.com/AztecProtocol/aztec-packages/issues/9101) |
| Owners               | @Maddiaa0                              |
| Approvers            | @MirandaWood @just-mitch @LHerskind @PhilWindle  |
| Target Approval Date | 2024-11-22                        |


## Executive Summary

Post https://github.com/AztecProtocol/aztec-packages/pull/9302, we will fully transition the node infrastructure read transaction effects from calldata to blobs.
See https://github.com/AztecProtocol/engineering-designs/pull/21 for background information on how blobs work.

## Introduction

<!-- Briefly describe the problem the work solves, and for whom. Include any relevant background information and the goals (and non-goals) of this implementation. -->

Transition the node to use blobs, fully remove our dependence on calldata when syncing transaction effects from L1.

There are a number of infrastructure related changes that are required to "complete" the blob integration. The primary concerns are:
- Nodes must request blobs from the "consensus layer" (CL) rather than from l1 (anvil is no longer suitable for syncing)
- Blobs are stored on the consensus layer for a ~3 week period, so a robust service must exist to serve blobs information post CL expiration.
- A way for nodes to request block information for their initial sync ( with an alternative solution that they can request this information OUT of protocol, and check the blob hashes 
 against long lived hashes that are published to l1 calldata. )
- Testing infrastructure must be updated to support the new blob service
    - End to end protocol integration tests
    - More advanced configurations tested in the cluster setting

### Goals
We want to remove the `body` field from the `propose` function inputs, leaving only the `blobInput` field.

```diff
  /**
   * @notice  Publishes the body and propose the block
   * @dev     `eth_log_handlers` rely on this function
   *
   * @param _header - The L2 block header
   * @param _archive - A root of the archive tree after the L2 block is applied
   * @param _blockHash - The poseidon2 hash of the header added to the archive tree in the rollup circuit
   * @param _signatures - Signatures from the validators
   * // TODO(#9101): The below _body should be removed once we can extract blobs. It's only here so the archiver can extract tx effects.
   * @param _body - The body of the L2 block
   * @param _blobInput - The blob evaluation KZG proof, challenge, and opening required for the precompile.
   */
  function proposeAndClaim(
    bytes calldata _header,
    bytes32 _archive,
    bytes32 _blockHash,
    bytes32[] memory _txHashes,
    SignatureLib.Signature[] memory _signatures,
  - bytes calldata _body,
    bytes calldata _blobInput,
    EpochProofQuoteLib.SignedEpochProofQuote calldata _quote
  ) external override(IRollup) {
    propose(_header, _archive, _blockHash, _txHashes, _signatures, _body, _blobInput);
    claimEpochProofRight(_quote);
  }
```

### Non Goals
- We do not want to impact the internal developer experience when running the end to end tests. 
- We do not want any changes to the Node interface. 

## Interface

<!-- Who are your users, and how do they interact with this? What is the top-level interface? -->

### Changes to node configuration
Node operators will need to provide an additional configuration value; pointing at an ethereum consensus layer node (CL).

```
L1_CONSENSUS_LAYER_URL
```

### Fetching Blobs

#### Request format
The CL implements a HTTP api to retrieve information, the following url can be used to fetch blob sidecars:

HTTP GET
```
/eth/v1/beacon/blob_sidecars/{block_id}
```
[See the beacon chain API](https://ethereum.github.io/beacon-APIs/?urls.primaryName=dev#/Beacon/getBlobSidecars)


#### Response Format


A method will be added to the archiver that will request given blob sidecars based on the blob id that the propose transaction was included in.

```
{
  "version": "deneb",
  "execution_optimistic": false,
  "finalized": false,
  "data": [
    {
      "index": "1",
      "blob": "<BLOB DATA>",
      "kzg_commitment": "0x93247f2209abcacf57b75a51dafae777f9dd38bc7053d1af526f220a7489a6d3a2753e5f3e8b1cfe39b56f43611df74a",
      "kzg_proof": "0xaE92B6fBE8a11bEEa293fa8C72Dfabae82A86e1d931aDCD9b57eaADF96B3969fab23aefE4cf5Ae4446ACf8bEcd4443fe",
      "signed_block_header": {
        "message": {
          "slot": "1",
          "proposer_index": "1",
          "parent_root": "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
          "state_root": "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
          "body_root": "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2"
        },
        "signature": "0x1b66ac1fb663c9bc59509846d6ec05345bd908eda73e670af888da41af171505cc411d61252fb6cb3fa0017b679f8bb2305b26a285fa2737f175668d0dff91cc1b66ac1fb663c9bc59509846d6ec05345bd908eda73e670af888da41af171505"
      },
      "kzg_commitment_inclusion_proof": [
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2",
        "0xcf8e0d4e9587369b2301d0790347320302cc0943d5a1884560367e8208d920f2"
      ]
    }
  ]
}
```


#### Emulating this service
In order to not degrade the performance of our end to end tests, we will add a lightweight service that emulate the api described above, such that we can avoid spinning up 
a consensus layer node when running end to end tests. Furthermore, with minor modifications ( storage persistence + indexing of block number) this database can be deployed into a production service to facilitate fast syncing without pinging nodes across the p2p network. 

This is safe as the node will check blobs against the blob commitment provided on l1. This code has already been included as part of https://github.com/AztecProtocol/aztec-packages/pull/9302. 

TODO(9101) includes changes to be made in response to this eng design.
```ts
  const blockBody = Body.fromBuffer(Buffer.from(hexToBytes(bodyHex)));

  const blockFields = blockBody.toBlobFields();
  // TODO(#9101): The below reconstruction is currently redundant, but once we extract blobs will be the way to construct blocks.
  // The blob source will give us blockFields, and we must construct the body from them:
  // TODO(#8954): When logs are refactored into fields, we won't need to inject them here.
  const reconstructedBlock = Body.fromBlobFields(
    blockFields,
    blockBody.noteEncryptedLogs,
    blockBody.encryptedLogs,
    blockBody.unencryptedLogs,
    blockBody.contractClassLogs,
  );

  if (!reconstructedBlock.toBuffer().equals(blockBody.toBuffer())) {
    // TODO(#9101): Remove below check (without calldata there will be nothing to check against)
    throw new Error(`Block reconstructed from blob fields does not match`);
  }

  // TODO(#9101): Once we stop publishing calldata, we will still need the blobCheck below to ensure that the block we are building does correspond to the blob fields
  const blobCheck = new Blob(blockFields);
  if (blobCheck.getEthBlobEvaluationInputs() !== blobInputs) {
    // NB: We can just check the blobhash here, which is the first 32 bytes of blobInputs
    // A mismatch means that the fields published in the blob in propose() do NOT match those in the extracted block.
    throw new Error(
      `Block body mismatched with blob for block number ${l2BlockNum}. \nExpected: ${blobCheck.getEthBlobEvaluationInputs()} \nGot: ${blobInputs}`,
    );
  }
```

We will replace getting the blockBody from the bodyHex, which is retrieved from the l1 propose transaction, and replace it with a request to the endpoint on the CL (or emulator) above.


#### Request Response Modifications (Optional Extension)
If they choose to, nodes should be able to sync without a dependence on a centralized provider. To facilitate this, we can extend the Request Response Framework defined in [9101-request-response](../9101-request-response/design.md). 

```
/aztec/req/txeffects/{version}
```

This request will have the following format:

- Request
```ts
interface TxEffectRequest {
    blockNumber: number
}
```

- Response
```ts
interface TxEffectResponse {
    blobs: [Blob]
}

interface Blob {
    fields: [Fr_BLS12_381, 4096]
    kzgCommitment: Buffer
    zkgProof: Buffer
}
```

#### For Spartan Deployments
Spartan Deployments already use a "real" L1 execution node underneath, we will extend the spartan cluster to run an ethereum consensus layer service. This will involve setting up a link between the execution layer node and consensus layer node via the engine API. 

In our current spartan configuration which has an L1 execution client underneath, it runs in a --dev configuration. This means that it does not perform any interactions with Ethereum's Consensus Layer. These consensus clients decide what blocks are part of the chain, while execution clients only validate blocks and transactions with respect to the world state. 

EL <> CL communication happens over the engine api, exposed (by default) on the EL port 8551. Connection between the CL and EL is authenticated via a JWT using a jwt secret set by the EL. 

Spartan deployments will need to be modified to generate a JWT for the execution layer, and provide it in the CL configuration, such that they can communicate in an authenticated manner.

<!-- ## Implementation -->

<!-- Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces. -->

<!-- Discuss any alternative or rejected solutions. -->


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
- [ ] Rollup Circuits
- [x] L1 Contracts
- [ ] Prover
- [ ] Economics
- [x] P2P Network
- [x] DevOps

## Test Plan

<!-- Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used. -->

For end to end tests:
- We will mock the consensus layer provider with a `blob service` that mocks the CL (TODO INCLUDE) rpc urls. 

For native network tests:
- We will use the same mock CL service

For spartan tests:
- We will use a real CL and EL node in conjunction, if existing tests work, we are good to go.

Testing of this work will be considered complete when the existing end to end test suite passes with the removal of broadcasting `TxEffects` as part 
of calldata with the `propose` payload.

## Documentation Plan

<!-- Identify changes or additions to the user documentation or protocol spec. -->

Include documentation on the new configuration value, and describe the additional service that will be run with the sandbox to serve blob data. Existing sandbox documentation will need to be extended to demonstrate how to retrieve blob data from the mocked service ( using the CL node apis ).

Node operator documentation will need to be updated to include the value they should set the `L1_CONSENSUS_LAYER_URL` value to.

## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.



## Tickets
- Add configuration value to nodes to add a consensus layer endpoint - https://github.com/AztecProtocol/aztec-packages/issues/10052
- Add a blob caching service for use in end to end tests - https://github.com/AztecProtocol/aztec-packages/issues/10053
- Deploy the sandbox to run with an in container version of the blob caching service - https://github.com/AztecProtocol/aztec-packages/issues/10054
- Add a consensus layer node into spartan - https://github.com/AztecProtocol/aztec-packages/issues/10055
- Begin reading TxEffects data from the consensus layer - https://github.com/AztecProtocol/aztec-packages/issues/10056
- Provide a way for nodes to sync the chain without a dependence on calldata - https://github.com/AztecProtocol/aztec-packages/issues/10057
    - Request Response for block data
    - Sync from `snap` sync service - a publicly hosted database (this can be checked against the calldata)
- Remove `data` blob from the rollup - https://github.com/AztecProtocol/aztec-packages/issues/10058

## QUESTIONS
- Does the PXE read from L1, or does it just interface with the node itself?? 

- Investigate the use of Kurtosis to set up execution layer + consensus layer nodes
