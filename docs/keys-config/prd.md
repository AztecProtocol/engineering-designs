# Keys and Addresses Configuration Project Requirements Document

- Owner: @spalladino
- Approvers: @aminsammara @PhilWindle
- Related issues: https://github.com/AztecProtocol/aztec-packages/issues/16094

## Context

Validators currently configure their keys and coinbase values via the environment or command line. This is both prone to vulnerabilities and fails to allow for advanced configurations. We need to utilise key stores for this configuration.

## Keys and addresses

The system involves the following L1 keys and addresses for a given validator:

- `Attester`: Private key of the validator, used for signing block proposals and voting.
- `Withdrawer`: Private key used for withdrawing staked funds. It is NOT used within the node.
- `Coinbase`: Ethereum Address set in a block proposal. L1 rewards and fees are sent to this address.
- `Fee Recipient`: Aztec Address of the block builder. Allows sending funds to the current block proposer in L2.
- `BLS Keys`: Public BLS keys for the validator. Not used for now, may be used in the future by replacing the attester keys.
- `Relayer Keys`: One or more private keys used exclusively for sending txs to L1. Do not have any significance within the protocol.

## Requirements and considerations

- A node operator may run more than a single validator.
- A node operator may act as an infrastructure provider, running validators for more than a single validator.
- A node operator may want to keep their validators separate, without revealing that they are being run from the same node.
- A node operator may want to use a remote signer rather than exposing their private keys to the node.

## Format

We define a keystore to be a JSON file with the following structure. To satisfy the requirement of handling configurations from different validators, a node operator may define one or more keystore files.

```ts
type KeyStore = {
  /** Schema version of this keystore file (initially 1). */
  schemaVersion: number;
  /** Validator configurations. */
  validators?: ValidatorKeyStore[];
  /** One or more accounts used for creating slash payloads on L1. Does not create slash payloads if not set. */
  slasher?: EthAccounts;
  /** Default url for the remote signer for all accounts in this file. */
  remoteSigner?: Url;
  /** Prover configuration. Only one prover configuration is allowed. */
  prover?: ProverKeyStore;
};

type ValidatorKeyStore = {
  /**
   * One or more validator attester keys to handle in this configuration block.
   * An attester address may only appear once across all configuration blocks across all keystore files.
   */
  attester: EthAccounts;
  /**
   * Coinbase address to use when proposing an L2 block as any of the validators in this configuration block.
   * Falls back to the attester address if not set.
   */
  coinbase?: EthAddress;
  /**
   * One or more EOAs used for sending block proposal L1 txs for all validators in this configuration block.
   * Falls back to the attester account if not set.
   */
  publisher?: EthAccounts;
  /**
   * Fee recipient address to use when proposing an L2 block as any of the validators in this configuration block.
   */
  feeRecipient: AztecAddress;
  /**
   * Default url for the remote signer for all accounts in this block.
   */
  remoteSigner?: Url;
};

type ProverKeyStore =
  | {
      /** Address that identifies the prover. This address will receive the rewards. */
      id: EthAddress;
      /** One or more EOAs used for sending proof L1 txs. */
      publisher: EthAccounts[];
    }
  | EthAccount;

/** One or more L1 accounts */
type EthAccounts = EthAccount | EthAccount[];

/** An L1 account is either a private key or a remote signer configuration */
type EthAccount = EthPrivateKey | EthRemoteSignerConfig;

/** A remote signer config can be set as just the address, in which case the signer url is sourced from the default set in the parent node. */
type EthRemoteSignerConfig =
  | { remoteSigner: Url; address: EthAddress }
  | EthAddress;

/** A private key is a 32-byte 0x-prefixed hex */
type EthPrivateKey = Hex<32>;

/** An address is a 20-byte 0x-prefixed hex */
type EthAddress = Hex<20>;

/** An Aztec address is a 32-byte 0x-prefixed hex */
type AztecAddress = Hex<32>;
```

## Examples

A keystore for a single validator:

```js
{
  schemaVersion: 1,
  validators: [
    {
      attester: '0x1234567890123456789012345678901234567890123456789012345678901234',
      feeRecipient: '0x1234567890123456789012345678901234567890123456789012345678901234',
    }
  ]
}
```

A keystore for two validators, one with a set of relayers, with their private keys stored in a remote signer:

```js
{
  schemaVersion: 1,
  remoteSigner: 'https://localhost:8080',
  slasher: '0x1234567890123456789012345678901234567890',
  validators: [
    {
      // Attester private key is stored in the remote signer in localhost:8080
      attester: '0x1234567890123456789012345678901234567890',
      // One relayer is defined as a private key, another as an account that goes to the default remote signer, another goes to another signer
      relayers: [
        '0x1234567890123456789012345678901234567890123456789012345678901234',
        '0x1234567890123456789012345678901234567890',
        { remoteSigner: 'https://localhost:8081', address: '0x1234567890123456789012345678901234567890' }
      ]
      feeRecipient: '0x1234567890123456789012345678901234567890123456789012345678901234',
    },
    {
      attester: '0x1234567890123456789012345678901234567890',
      feeRecipient: '0x1234567890123456789012345678901234567890123456789012345678901234',
    },
  ]
}
```

A keystore for a prover that sends proofs from their prover address directly:

```js
{
  schemaVersion: 1,
  prover: '0x1234567890123456789012345678901234567890123456789012345678901234'
}
```

A keystore for a prover with two relayers:

```js
{
  schemaVersion: 1,
  prover: {
    id: '0x1234567890123456789012345678901234567890',
    publisher: [
      '0x1234567890123456789012345678901234567890123456789012345678901234',
      '0x1234567890123456789012345678901234567890123456789012345678901234'
    ]
  }
}
```

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
