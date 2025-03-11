# Inactivity Leak Project Requirements Document

- Owner: @spalladino
- Approvers:
  - @aminsammara
  - @charlielye
  - @PhilWindle
  - @maddiaa
  - @LHerskind

## Background

We currently have a slashing mechanism built on top of governance, where sequencers can vote to slash a node if agreed. Issue with this approach is that slashing takes time, and incentives (ie not wanting to lose money!) play a big role in it.

However, during early testnet phases, where nodes do not have so much at stake, and failures are to be expected, we want to slash fast to ensure we don't halt block production due to a significant portion of validators being offline.

So, for testnet only, we want to have a centralized entity who can rapidly slash or kick out validators from the set. This process can be manual, but we need to provide the slasher with accurate info on who to slash.

## Desired User Flow

The testnet Aztec Slasher (or AS for short, after their initials) must be able to gather all info needed for slashing from an Aztec Node under their control. Note that given slashing is centralized, we can use information from a single trusted node to decide who to slash.

AS should be able to access this information either via a dashboard, or by hitting their node RPC interface and getting the data in JSON format. It must be immediately clear what nodes needs to be slashed from this data. For example:

```
$ curl -XPOST https://my-node/ -d'{"method": "node_getSlashable"}'
{
    "synchedTo": { "l1Block": 1, "l2Block": 1, "l2BlockHash": "0xabcd" } ,
    "validators": [
        { "address": "0x01", "lastBlockProposedAt": "2025-01-01T01:01:01", "lastBlockAttestedAt": "2025-01-01T01:01:01", "missedAttestationsStreak": 20, "missedProposalsStreak": 5, "missedProposalsRate": 0.1, "missedAttestationsRate": 0.2, "joinecAt": "2025-01-01T01:01:01" }
    ]
}
```

Once the addresses to slash have been gathered, AS, using a set of privileged L1 keys, should be able to call the L1 slasher contract to execute the slash in a single tx. This should be either executed through the Aztec CLI, or the Aztec CLI should generate the payload to run through cast. For example:

```
$ aztec slash --slasher-client-address 0xabcd --private-key 0x1234 0x01 0x02
```

## Requirements

- Data must be clear on which addresses must be slashed, clear on why the addresses were selected, and must be updated every epoch.
- Given a minimum number of `1` active and online validator, the network MUST always eventually resume block building regardless of how many other validators went offline.

### Identifying slashable validators

- Consider both block proposals and attestations.
- Missed attestations and proposals are reported both as current streak and rolling average.
  - Current streak is defined as the number of missed attestations or proposals since the last activity. This is useful for detecting non-malicious validators that may be offline.
  - Rolling average is defined as the number of missed attestations or proposals over the total expected for the last N epochs, where N is configurable and defaults to 50. This will be useful for detecting malicious or unreliable validators long-term.
- Attestations should be gathered from both L1 and the p2p attestation pool.
  - Rationale is that block proposers post to L1 only the attestations they need, so we need to look into the attestation pool to gather all of them. We also look into L1 since our node is not guaranteed to receive all attestations via p2p in case of a p2p issue.
- Proposals should be gathered from both L1 and the p2p attestation pool.
  - Rationale is that if a proposal cannot be posted due not not enough attestations (because more than 1/3 of the committee is down) we don't want to punish the proposer.
- List of slashable validators should include all validators that have missed at least one attestation or proposal (since their time of last activity).
  - AS should then filter the resulting data based on how aggressive they want to be in slashing, using `jq` or a script.
- An address that fulfilled all their duties but had no activity due to not being selected for a committee must not be selected to be slashed.
- A validator selected for attestation must not be counted towards a missed attestation if there was no proposal seen for that slot.
