# Validator BLS Keys Design Document

- Owner: @spalladino
- Approvers: @LHerskind, @iAmMichaelConnor

## Summary

We have identified potential gas savings from aggregating signatures, both for L2 block proposals (by aggregating block attestations) and for voting (by aggregating votes). Regardless of whether we implement these gas savings now, we want to freeze governance code soon, so we propose future-proofing it by already adding support for validators to register BLS keys.

## Signing scheme and curve

The requirements for the signing scheme and curve are:

- An aggregated signature should be small (no more than 512 bits ideally) for a 48-validator committee.
- The cost of computing an aggregate key and verifying an aggregate signature should not be too expensive in the EVM (no more than 300k gas ideally). Note that, since the committee changes once per epoch, we need to compute a new aggregate key every epoch.
- Each individual public key should be small as well, since it will have to be read from storage for computing the committee commitment.
- At the moment, we do not require verifying these signatures on a rollup circuit, but this _may_ change in the future, so it should not be prohibitively expensive.

We propose that a BLS aggregate signature over the [BLS12-381](https://eth2book.info/latest/part2/building_blocks/bls12-381/) curve fits the bill. Public keys are 48 bytes long, aggregated signatures are 96 bytes long, and L1 verification should be doable in under the target gas:

> We need to send as CALLDATA the 48 pubkeys for the committee members plus a bitmap of signers, so we can reconstruct both the committee hash and the aggregated pubkey, which is roughly 48 words (`1536` bytes, `61k` gas at 40 gas per slot, or `24k` at 16 gas per slot). The verification itself requires two `SLOAD`s (`4200`), a hash-to-curve (`20k` gas), 33 ECADDs (`5k`), and two pairings (`124k` gas). Total is about `214k` gas, which gets paid once per epoch.

## Data types

We add a `BLSPublicKey` type, backed 48 bytes data, to fit a public key on the BLS12-381 curve. Along with this type, we add a method for validating that a given `BLSPublicKey` instance is a valid point in the curve.

## Interface changes

The following methods or structs require an additional `BLSPublicKey` field:

- `StakingQueue.enqueue`
- `StakingQueue.DepositArgs`
- `IStakingCore.deposit`
- `StakingLib.deposit`
- `RollupCore.deposit`
- `ExtRollupLib2.deposit`
- `GSE.deposit`
- `GSE.AttesterConfig`

All GSE functions that return a set of attester addresses now require an additional function for fetching their BLS keys:

- `GSE.getAttestersFromIndicesAtTime` -> `GSE.getAttestersBLSPubKeysFromIndicesAtTime`
- `GSE.getAttestersAtTime` -> `GSE.getAttestersBLSPubKeysAtTime`
- `GSE.getAttesterFromIndexAtTime` -> `GSE.getAttesterBLSPubKeyFromIndexAtTime`

## Security considerations

When registering a new key, we first need to validate that it is a correct public key in the curve. Then, as described in [this article](https://www.zellic.io/blog/bls-signature-versatility/#the-pitfall-of-multi-signatures), we need to guard against rogue key attacks. We have two options for that:

1. Require a proof of possession, validated along with the key during registration
2. Use a modified aggregate public key, which should only require 2 scalar multiplications

While the 2nd approach has not been implemented according to the article linked above, it sounds simple enough and the additional gas cost is low.

## Open questions

### Is the choice of curve correct?

We defaulted to the curve used by ZCash and Ethereum consensus, but there may be other curves that are a better fit.

### When should we validate the public key is valid?

The innermost contract (GSE) seems to be the most secure place where to execute this validation.

On the other hand, if we know that all entries to GSE have to go through the staking queue, we could instead validate early in the `enqueue`, which would also allow us to change curves in the future without having to modify the GSE.

To favor failing fast, I prefer validating in the queue, assuming we are certain that the queue is always present.

### How to prevent against the rogue key attack?

As discussed above in the Security Considerations section, we need to decide between requiring a proof of possession or using a modified aggregate public key.

### How do we generate the BLS private key for validators?

We could derive the BLS private key from their ECDSA private key, potentially from having them sign a given message so we do not need direct access to the ECDSA private key. This means that validators do not need to store two separate private keys. Note that this requires **deterministic** ECDSA signatures, which not every hardware wallet supports.

We need to validate whether this is feasible and secure.

### Should we support rotation of the BLS keys?

If we do not default to generating the BLS private key from the validator ECDSA private key, should we allow validators to change them? It's unclear if rotating should involve a forced delay, so that a validator cannot change their BLS key halfway through an epoch.

To avoid additional complexity, I suggest not to. Worst case, a validator can exit and re-enter with different BLS keys.

### Should we support changing key family in the future?

If we find a better signing algorithm or curve in the future, we have no easy way for validators to switch key scheme. This would require each validator to have both set of keys (the old and new ones) registered simultaneously, so when the canonical rollup instance is changed, the new one can immediately access the new keys.

Doing this would require:

- Having a variable-length field in the GSE for storing "validation keys", where we can store arbitrary data, such as multiple keys from different families packed into the same buffer. This means slightly larger gas costs, since accessing a variable-length byte array is slightly more expensive than a fixed-length one.
- Having a way for validators to update their "validation keys", so they can register the keys for the new family when needed (see "Should we support rotation" above).

Given the additional complexity, I vote for not doing this and choosing a single key family.

## See also

- @LHerskind's notebook [BLS signature investigation](https://colab.research.google.com/drive/1gXbNXLuQZw_1n7PhkRVlTGFl69iIjkNE (uses bn254)
- @kobigurk notes on [Optimized BLS multisignatures on EVM](https://hackmd.io/7B4nfNShSY2Cjln-9ViQrA)

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
