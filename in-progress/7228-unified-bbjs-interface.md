| -------------------- | --------------------------------- |
| Issue | [Unified bb.js interface that delegates to wasm or native via CLI](https://github.com/AztecProtocol/aztec-packages/issues/7228) |
| Owners | @spalladino |
| Approvers | @codygunton @ludamad @PhilWindle @TomAFrench @charlielye |

## Executive Summary

We want bb.js to expose a unified proving and verifying interface that delegates to either wasm or native, depending on the context (web vs node). The updated bb.js should also provide the CLI entrypoint for proving and verifying during Noir development, replacing native bb, and provide a simplified interface similar to that of noir-js-backend-barretenberg.

**The goal of this document is to agree on the common interface.**

## Introduction

Making bb.js the main entrypoint for interacting with bb, either wasm or native, will allow us to:

- Iterate the CLI on bb.js instead of cpp
- Provide an easier unified programmatic interface to clients
- Consolidate code currently spread across bb.js, noir-js-backend-bb, and aztec's bb-prover
- Transparently change how we communicate with native bb by keeping it hidden behind bb.js (we can go from calling the native CLI into calling a long-running process via a nicer binary interface)
- Simplify the installation process for the user (downloading the native extension would be handled by the bb.js npm package)

## Usage scenarios

We expect to use this API for proving and verifying:

- In a node.js app (like Aztec's prover)
- In a webapp
- Via the bb.js CLI for local Noir development

## Approach

The bb wasm API and the bb CLI API are different in nature. The wasm API is more fine-grained, since it can make use of a long-lived bb instance that caches compiled circuits and keys. It also exposes functions unrelated to proving, such as hashing, signing, and other cryptographic primitives. On the other hand, the CLI API bundles together common proving operations, as it is stateless and it benefits from reducing the total number of calls for each operation.

Since we don't have plans on reworking bb as a long-running native process now, we are limited to communicate with native bb via its CLI, so we'll shoot for a coarse API. This should also be simpler for users to work with. Eventually, if we implement the long-running native bb process, we can provide a more fine-grained API, and reimplement the one in this doc via multiple calls to it.

For the design, we gather "inspiration" from the native CLI, the bb.js CLI, the noir-js-bb-backend, and the Aztec bb-prover.

## Interface and implementation

We propose the following interface, to be implemented via the native CLI and wasm as described below.

### Types

#### `Circuit`

Circuit bytecode in ACIR format.

#### `Witness`

Binary witness as outputted by the ACVM simulator.

#### ~~`PathOrData`~~

Either a path to the filesystem or the actual contents. This would allow us to propagate paths to disk from the bb.js interface into the native bb, instead of having to read a file into memory from bb.js just to conform to the shared interface, and then write again to disk to call the native bb CLI.

:question: We discarded this type for simplicity reasons, but there are reasons to keep it. Even after we discard the native CLI, we may still want to just point native bb to disk as a means to share data between bb.js and bb, especially if we cache more aggressively.

#### `Flavor`

Specifies the proving system for the proof. Not all methods may be supported for all flavors, either because of limitations (eg AVM is not supported in wasm) or because it doesn't make sense (eg there is a single AVM verification key). Valid values:

- `UltraPlonk`
- `UltraHonk`
- `MegaHonk`
- `ClientIVC`
- `AVM`

:question: I collected these values from scanning the bb CLI interface. Are they correct? Should we only target a subset of them? Is "flavor" the correct term? Should we spell it properly as "flavour"?

### Interface

#### `prove(circuit: Circuit, witness: Witness, flavor: Flavor): { proof: Buffer }`

Proves a given circuit with the given witness as input. Returns the proof in raw binary format.

Native implementation:

- `bb prove | prove_ultra_honk | prove_mega_honk | avm_prove | client_ivc_prove_output_all` (there is no `client_ivc_prove`)

Wasm implementation (`AVM` not supported)

- `acirGetCircuitSizes`
- `commonInitSlabAllocator`
- `srsInitSrs`
- `acirNewAcirComposer`
- `acirInitProvingKey`
- `acirCreateProof | acirProveUltraHonk | acirProveAndVerifyMegaHonk | acirFoldAndVerifyProgramStack` (there is no `acirProveMegaHonk`, hence the `acirProveAndVerifyMegaHonk`)

#### `proveForRecursion(circuit: Circuit, witness: Witness, flavor: Flavor): { proof: Buffer, proofAsFields: Fields, vk: Buffer, vkAsFields: Fields }`

Proves a given circuit with the given witness as input. Returns the proof in raw binary and fields format, as well as the verification key in binary and fields format. Useful for generating a proof that then needs to be fed into a subsequent circuit.

Native implementation (`AVM` not supported)

- `bb prove_output_all | prove_ultra_honk_output_all | prove_mega_honk_output_all | client_ivc_prove_output_all`

Wasm implementation (`AVM, ClientIVC, MegaHonk` not supported)

- `acirGetCircuitSizes`
- `commonInitSlabAllocator`
- `srsInitSrs`
- `acirNewAcirComposer`
- `acirInitProvingKey`
- `acirCreateProof | acirProveUltraHonk`
- `acirSerializeProofIntoFields | acirProofAsFieldsUltraHonk`
- `acirGetVerificationKey`
- `acirSerializeVerificationKeyIntoFields`

:question: Do we really need this method? Is there a significant gain over calling `prove + getProofAsFields + getVerificationKey` on the bb CLI? We're using it today on bb-prover mostly.

#### `getProofAsFields(proof: Buffer, numPublicInputs: number, flavor: Flavor): { proofAsFields: Fields }`

Given a proof in raw binary format, returns it formatted as fields. Required for generating the recursive artifacts for recursive proving, along with the verification key as fields. Requires calling `prove` first. Note that we need to keep this method separate from `prove` since it could be different users who create the inner proof and who want to convert it to fields (see [Noir docs](https://noir-lang.org/docs/dev/how_to/how-to-recursion/#step-3---verification-and-proof-artifacts)).

:question: Can we reimplement this logic on ts-land? We've received conflicting responses to this.

Native implementation (does not support `ClientIVC, AVM`)

- `bb proof_as_fields | proof_as_fields_honk` (assumes `_honk` supports both Ultra and Mega)

Wasm implementation (does not support `ClientIVC, AVM, MegaHonk`)

- `srsInitSrs(Crs(1))`
- `acirNewAcirComposer(0)`
- `acirSerializeProofIntoFields | acirProofAsFieldsUltraHonk`

#### `getVerificationKey(circuit: Circuit, flavor: Flavor): { vk: Buffer, vkAsFields: Fields }`

Computes the verification key for a given circuit. Returns the verification key in binary and as fields, which allows the client to read its hash and the number of public inputs for the circuit. Users should call this once per circuit they want to verify, and reuse it for verifying as many proofs as needed.

:question: Can we avoid returning `vkAsFields`, and convert from binary to fields in ts-land?

Native implementation (`ClientIVC, AVM` not supported)

- `bb write_vk | write_vk_ultra_honk | write_vk_mega_honk`
- `bb vk_as_fields | vk_as_fields_ultra_honk | vk_as_fields_mega_honk`

Wasm implementation (only `UltraPlonk` supported)

- `acirGetCircuitSizes`
- `commonInitSlabAllocator(size)`
- `srsInitSrs(size)`
- `acirInitProvingKey`
- `acirGetVerificationKey`
- `acirSerializeVerificationKeyIntoFields`

#### `verify(proof: Buffer, vk: Buffer, flavor: Flavor): { isValid: boolean }`

Verifies the given proof, which includes public inputs, against the given verification key. Both proof and vk are in raw binary format. Requires the output of `getVerificationKey` for the given circuit first.

Native implementation (`ClientIVC` not supported)

- `bb verify | avm_verify | verify_ultra_honk | verify_mega_honk`

Wasm implementation (`ClientIVC, MegaHonk, AVM` not supported)

- `srsInitSrs(Crs(1))`
- `acirNewAcirComposer(0)`
- `acirLoadVerificationKey`
- `acirVerifyProof | acirVerifyUltraHonk`

#### `getSolidityVerifier(vk: Buffer, flavor: Flavor): { contract: Buffer }`

Generates a Solidity verifier contract for the given verification key in raw binary format. Only `UltraPlonk` is supported. Expected to be called once per circuit during development. Requires the output of `getVerificationKey`.

Native implementation:

- `bb contract`

Wasm implementation:

- `srsInitSrs(Crs(1))`
- `acirNewAcirComposer(0)`
- `acirLoadVerificationKey`
- `acirGetSolidityVerifier`

#### `getGateCount(circuit: Circuit, flavor: Flavor): { gates: number }`

Counts the number of gates for a given circuit.

Native implementation:

- `bb gates`

Wasm implementation:

- `acirGetCircuitSizes`

:question: `bb` exposes a single method to get gates with just a boolean "honk recursion". Does this mean that for `UltraPlonk` we can get circuit sizes setting this flag to false, and for `UltraHonk` and `MegaHonk` we set it to true? How about `ClientIVC`? And for `AVM` does it even make sense to ask about gate count?

### Non-Interface

Methods that are today part of the interface in the bb.js or bb CLIs but we are leaving them out of this shared interface.

#### `proveAndVerify(circuit: Circuit, witness: Witness, flavor: Flavor): { isValid: boolean }`

Proves a circuit against the given witness, and verifies it immediately. Returns whether the result was valid.

Can be implemented at a high-level by calling `prove`, `getVerificationKey`, and `verify`.

#### `getVerificationKeyAsFields(vk: Buffer): { vkAsFields: Fields}`

Given a verification key in raw binary format, returns it as fields.

We should not need this method since we make all methods that return a vk (`proveForRecursion` and `getVerificationKey`) return it in both formats (assuming we cannot reimplement the `vkAsFields` in ts).

#### `getProvingKey(circuit: Circuit, flavor: Flavor): { pk: Buffer, pkAsFields: Fields }`

Given a circuit, returns its proving key both in binary and as fields.

Tests suggest that loading a proving key takes as much as generating it on the fly, so there is no point to generating and storing a proving key. If this changes, we may want to add this method, and modify the `prove` and `proveForRecursion` methods to accept a proving key as well as a circuit.

### Statefulness

The proposed API is stateless. This mimics the bb.js CLI, as well as the native CLI as we're using them today from `bb-prover`. Wasm implementations should always call `destroy` at the end of each operation.

However, this means that we lose the benefit of a long-running bb process (available only in wasm today) that can keep a circuit's gates in-memory. This is valuable in a scenario where we want to create multiple proofs for the same circuit using different witnesses.

As an alternative, and following noir-js-bb-backend design, we could move the `prove` and `proveForRecursion` methods into a different `BarretenbergProver` interface, which holds the circuit in memory until it's terminated. This means the prove methods become:

- `prove(witness: Witness): { proof: Buffer }`
- `proveForRecursion(witness: Witness): { proof: Buffer, proofAsFields: Fields, vk: Buffer, vkAsFields: Fields }`

And are accessible from a `Prover` object that requires the `circuit` and `flavor` to be created.

## Bundling

Since it is now bb.js responsibility to install the native bb package, we'd need an `install` script (ie script that is automatically triggered when the package is installed) in the bb.js `package.json` that mimics `bbup` behaviour and installs the binary that corresponds to the npm package version and current platform, only that it is downloaded local to the package instead of in the user's home.

## Change Set

- bb.js
- noir-js-backend-barretenberg
- bb-prover

## Test Plan

TBD

## Documentation Plan

- Update [Noir documentation](https://noir-lang.org/docs/dev/getting_started/barretenberg/) on how to install bb and prove and verify circuits.
- :question: Are there public API docs for bb?

## Rejection Reason

We're shifting our goal to having a common interface for WASM and native via IPC in bb itself, not as a wrapper in bb.js. This changes the design so that the API must be granular and stateful, given native invocation will not happen via CLI.
