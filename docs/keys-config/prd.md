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
	/** Default config for the remote signer for all accounts in this file. */
	remoteSigner?: EthRemoteSignerConfig;
	/** Prover configuration. Only one prover configuration is allowed. */
	prover?: ProverKeyStore;
	/** Used for automatically funding publisher accounts if there is none defined in the corresponding  ValidatorKeyStore*/
	fundingAccount?: EthAccount;
};

type ValidatorKeyStore = {
	/**
	 * One or more validator attester keys to handle in this configuration block.
	 * An attester address may only appear once across all configuration blocks across all keystore files.
	 */
	attester: EthAccounts;
  /** 
   * One or more BLS attester keys to handle in this configuration block.
   * These keys map 1 to 1 with the attester accounts above.
   * So for example, if a mnemonic is used here it should specify the same number of keys as in 'attester'.
   */
  blsAttester?: BLSAccounts;
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
	 * Default remote signer for all accounts in this block.
	 */
	remoteSigner?: EthRemoteSignerConfig;
	/**
	 * Used for automatically funding publisher accounts in this block.
	 */
	fundingAccount?: EthAccount;
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
type EthAccounts = EthAccount | EthAccount[] | EthMnemonicConfig;

/** One or more BLS accounts */
type BLSAccounts = BLSAccount | BLSAccount[] | BLSMnemonicConfig;

/** A mnemonic can be used to define a set of accounts */
type MnemonicConfig = {
	mnemonic: string;
	addressIndex?: number;
	accountIndex?: number;
	addressCount?: number;
	accountCount?: number;
};

type EthMnemonicConfig = MnemonicConfig;
type BLSMnemonicConfig = MnemonicConfig;

/** An L1 account is a private key, a remote signer configuration, or a standard json key store file */
type EthAccount =
	| EthPrivateKey
	| EthRemoteSignerAccount
	| EthJsonKeyFileV3Config;

type BlsAccount = 
  | BLSPrivateKey
  | BLSJsonKeyFileV3Config;

/** A remote signer is configured as an URL to connect to, and optionally a client certificate to use for auth */
type EthRemoteSignerConfig =
	| Url
	| { remoteSignerUrl: Url; certPath?: string; certPass?: string };

/**
 * A remote signer account config is equal to the remote signer config, but requires an address to be specified.
 * If only the address is set, then the default remote signer config from the parent config is used.
 */
type EthRemoteSignerAccount =
	| EthAddress
	| {
			address: EthAddress;
			remoteSignerUrl: Url;
			certPath?: string;
			certPass?: string;
	  };

/** A json keystore config points to a local file with the encrypted private key, and may require a password for decrypting it */
type JsonKeyFileV3Config = { path: string; password?: string };
type EthJsonKeyFileV3Config = JsonKeyFileV3Config;
type BLSJsonKeyFileV3Config = JsonKeyFileV3Config;


/** A private key is a 32-byte 0x-prefixed hex */
type EthPrivateKey = Hex<32>;

type BLSPrivateKey = Hex<32>

/** An address is a 20-byte 0x-prefixed hex */
type EthAddress = Hex<20>;

/** An Aztec address is a 32-byte 0x-prefixed hex */
type AztecAddress = Hex<32>;
```

### Mnemonic

The `EthMnemonicConfig` accepts a seed phrase and by default derives the private key at `m/44'/60'/0'/0/0` based on [BIP44](https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki). Setting a different address or account index change the corresponding level, and setting a different count generates multiple keys starting on the specified index.

| Address Index | Address Count | Account Index | Account Count | Resulting Derivation Paths                                                     |
| ------------- | ------------- | ------------- | ------------- | ------------------------------------------------------------------------------ |
|               |               |               |               | `m/44'/60'/0'/0/0`                                                             |
| 3             |               |               |               | `m/44'/60'/0'/0/3`                                                             |
|               |               | 5             |               | `m/44'/60'/5'/0/0`                                                             |
| 3             |               | 5             |               | `m/44'/60'/5'/0/3`                                                             |
| 3             | 2             | 5             |               | `m/44'/60'/5'/0/3`, `m/44'/60'/5'/0/4`                                         |
| 3             | 2             | 5             | 2             | `m/44'/60'/5'/0/3`, `m/44'/60'/5'/0/4`, `m/44'/60'/6'/0/3`, `m/44'/60'/6'/0/4` |

### Remote signer

The remote signer defines a [Web3Signer](https://docs.web3signer.consensys.io/) endpoint where the node sends requests for signing a transaction or a message. The signer is configured as a URL to connect to, and optionally a path to a client certificate file needed for authentication, along with the password for decrypting the certificate file.

### Json V3

The JsonV3 keyfile is a standard for storing encrypted ethereum private keys. The `EthJsonKeyFileV3Config` allows defining a path to a JsonV3 keyfile along with the password needed for decrypting it. The path may be a directory, in which case all json files within the directory are loaded.

## Examples

A keystore for a single validator. The attester is used as publisher:

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

A keystore for multiple validators, with their private keys stored in a remote signer:

```js
{
  schemaVersion: 1,
  // All attester private keys are stored in the remote signer in localhost:8080
  remoteSigner: 'https://localhost:8080',
  // This slasher private key is also stored in the remote signer
  slasher: '0x1234567890123456789012345678901234567890',
  validators: [
    {
      // One publisher is defined as a private key, another as an account that goes to the default remote signer, another goes to another signer
      attester: '0x1234567890123456789012345678901234567890',
      publisher: [
        '0x1234567890123456789012345678901234567890123456789012345678901234',
        '0x1234567890123456789012345678901234567890',
        { remoteSignerUrl: 'https://localhost:8081', address: '0x1234567890123456789012345678901234567890' }
      ]
      feeRecipient: '0x1234567890123456789012345678901234567890123456789012345678901234',
    },
    {
      // This attester sends txs using the attester account as publisher
      attester: '0x1234567890123456789012345678901234567890',
      feeRecipient: '0x1234567890123456789012345678901234567890123456789012345678901234',
    },
    {
      // This attester uses the publishers derived from a mnemonic
      attester: '0x1234567890123456789012345678901234567890',
      feeRecipient: '0x1234567890123456789012345678901234567890123456789012345678901234',
      publisher: { mnmemonic: "test test test test", addressCount: 4 }
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

A keystore for a prover with two publishers:

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
