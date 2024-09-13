# Proof Timeliness

|                      |                                                             |
| -------------------- | ----------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8401 |
| Owners               | @just-mitch                                                 |
| Approvers            | @LHerskind                                                  |
| Target Approval Date | 2024-09-13                                                  |


## Executive Summary

The rollup contract will require that the pending chain be pruned to the proven chain if a proof for an epoch does not get verified on L1 in a fixed amount of time.

## Introduction

There is functionality in the rollup contract to prune the pending chain, but this is not currently used.

A strict proof timeliness requirement affords guarantees to users that their transactions will be included in the proven chain within a fixed amount of time.

This design focuses on how those timelines are defined and enforced by the rollup contract; it does not cover how nodes will handle the ensuing reorg with respect to their local state.

## Proving phases

<!-- Editors: you can copy/paste the png from the repository into excalidraw to make edits. -->

![Proving Phases](./proving-phases.png)

### Proof claim phase

The beginning of each epoch is the "proof claim phase".

This phase has a duration of $C$ slots (e.g. 13 slots. See notebook for modeling).

During this time, the proposer for a slot can submit a claim to be the prover for the previous epoch.

This can be a transaction separate from the submission of their proposed block.

Doing so grants monopoly rights to the rewards for submitting the proof of epoch `n-1`:
if there are block rewards in test token TST, they will be sent to the address that submitted the claim.

If no claim is submitted, the pending chain is pruned to the tip of the proven chain;
a caveat is if a proof for epoch `n-1` is submitted during the proof claim phase.

### Proof production

The proof for epoch `n-1` must land in epoch `n`.

Failure to submit a proof results in the bond posted with the claim being slashed if it exists.

Further, the pending chain is pruned to the tip of the proven chain.

Given that an epoch is $E$ slots, the wall time duration of $E-C$ slots must be greater than the time required to produce a proof.

## The overall flow

```mermaid
sequenceDiagram
    participant Prover
    participant Proposer
    participant EscrowContract
    participant RollupContract
    participant TokenContract

    Prover->>EscrowContract: deposit(amount, deadline, v, r, s)
    EscrowContract->>TokenContract: permit(prover, escrow, amount, deadline, v, r, s)
    EscrowContract->>TokenContract: transferFrom(prover, escrow, amount)
    
    Note over Prover: Prover creates and signs a message off-chain
    Prover-->>Proposer: Communicate signed message (amount, fee, rollupContract, validUntil, signature)
    
    Proposer->>RollupContract: claimProofRight(prover, amount, fee, validUntil, signature)
    RollupContract->>EscrowContract: stakeBond(prover, amount, epoch, fee, rollupContract, validUntil, signature)

    Proposer->>RollupContract: proposeBlock(blockHash, archive)
    RollupContract->>RollupContract: _pruneIfNeeded()
    
    Note over Prover: Generates the proof of the epoch
    Prover->>RollupContract: submitProofOfEpoch(epochHeader)
    
    RollupContract->>EscrowContract: unstakeBond(prover, amount)
    
```

More details on the contents of the message signed and how it is communicated can be found in [the prover coordination design](https://github.com/AztecProtocol/engineering-designs/pull/25).

We use an external escrow contract to handle the bond to gain:
- a very specific/targeted permitting mechanism for the bond to be used, protecting the prover
- a delayed withdrawal mechanism for the bond, ensuring that proposers can be confident the bond will be available when they `claimProofRight`


## Rough Implementation

This is a rough, illustrative implementation of the proof timeliness requirement to guide intuition.  

The key "trick" is that we prune the pending chain as part of a proposer's block submission if needed.

An observation is that in the current design, the committee does not change in the event that no proof claim is posted for the previous epoch;
this means that the committee will have any blocks in its first $C$ slots reorged, but the subsequent blocks can start a new pending chain.

```solidity

interface IEscrowContract {
    function deposit(uint256 amount, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
    function stakeBond(address bondProvider, uint256 amount, uint256 epoch, uint32 fee, address rollupContract, uint256 validUntil, bytes memory signature) external;
    function unstakeBond(address bondProvider, uint256 amount) external;
    function withdraw(uint256 amount) external;
}


contract Rollup {
    struct ChainTip {
        uint256 blockNumber;
        uint256 slotNumber;
    }

    struct State {
        ChainTip pendingTip;
        ChainTip provenTip;
    }

    struct ProposalLog {
        bytes32 hash;
        uint256 slotNumber;
        bytes32 archive;
    }

    struct ProofClaim {
        address bondProvider;
        address rewardRecipient;
        uint256 claimedEpoch;
        uint256 basisPointFee;
    }

    struct Fee {
        address recipient;
        uint256 amount;
    }

    struct EpochHeader {
        uint256 finalBlockNumber;
        Fee[] fees;
    }

    // State variables
    State public state;
    mapping(uint256 => ProposalLog) public proposalLogs;
    ProofClaim public proofClaim;
    IProverBondEscrow public proverBondEscrow;
    IFeeJuicePortal public feeJuicePortal;

    // Constants
    uint256 public constant CLAIM_DURATION = 13;
    uint256 public constant EPOCH_DURATION = 32;
    uint256 public constant PROOF_COMMITMENT_BOND_AMOUNT = 100;

    // Events
    event ProofRightClaimed(address indexed claimer, uint256 indexed epoch);
    event PendingChainPruned(uint256 blockNumber, uint256 slotNumber);
    event ProofSubmitted(uint256 indexed epoch, uint256 finalBlockNumber);

    // Errors
    error Rollup__NonProposerCannotClaimProofRight();
    error Rollup__ProofRightAlreadyClaimed();
    error Rollup__NotInClaimPhase();
    error Rollup__NoProposalLog();
    error Rollup__NotPreviousEpoch();
    error Rollup__NotLastBlockInEpoch();
    error Rollup__ProofProductionPhaseEnded();
    error Rollup__UnauthorizedProofSubmitter();

    constructor(address _proverBondEscrow, address _feeJuicePortal) {
        proverBondEscrow = IProverBondEscrow(_proverBondEscrow);
        feeJuicePortal = IFeeJuicePortal(_feeJuicePortal);
    }

    // Will be called by the proposer.
    // Must have a permit from the provider of the bond.
    function claimProofRight(
        address _bondProvider,
        uint256 _bondAmount,
        uint32 _basisPointFee,
        uint256 _validUntil,
        bytes32 calldata _signature
    ) external {
        uint256 currentSlot = getCurrentSlot();
        uint256 currentEpoch = getCurrentEpoch();
        address currentProposer = getCurrentProposer();

        if (currentProposer != address(0) && currentProposer != msg.sender) {
            revert Rollup__NonProposerCannotClaimProofRight();
        }

        // Overwrite stale proof claims
        if (proofClaim.claimedEpoch == currentEpoch - 1) {
            revert Rollup__ProofRightAlreadyClaimed();
        }

        if (currentSlot % EPOCH_DURATION >= CLAIM_DURATION) {
            revert Rollup__NotInClaimPhase();
        }

        if (_bondAmount < PROOF_COMMITMENT_BOND_AMOUNT) {
            revert Rollup__InsufficientBondAmount();
        }

        // reverts if the signature is invalid
        // or bid is no longer valid
        // or the bond provider has insufficient balance
        escrow.stakeBond(_bondProvider, _bondAmount, currentEpoch, _basisPointFee, address(this), _validUntil, _signature);


        proofClaim = ProofClaim({
            rewardRecipient: currentProposer,
            bondProvider: _bondProvider,
            claimedEpoch: currentEpoch - 1,
            basisPointFee: _basisPointFee
        });

        emit ProofRightClaimed(proposer, proofClaim.claimedEpoch, currentSlot);
    }

    function _pruneIfNeeded() internal {
        uint256 currentSlot = getCurrentSlot();
        uint256 mostRecentProvenSlot = getMostRecentProvenSlot();
        if (currentSlot <= mostRecentProvenSlot + EPOCH_DURATION) {
            // we are in epoch `n`, and the proof for epoch `n-1` has been submitted
            return;
        } else if (currentSlot > mostRecentProvenSlot + 2 * EPOCH_DURATION) {
            // If we are more than 2 epochs ahead, prune immediately.
            // This will render the bond
            _prune();
            return;
        } else {
            // We are in epoch `n`, awaiting the proof for epoch `n-1`

            uint256 currentEpoch = getCurrentEpoch();
            uint256 currentEpochStartSlot = currentEpoch * EPOCH_DURATION;

            if (currentSlot < currentEpochStartSlot + CLAIM_DURATION) {
                // If we are in the claim phase, do not prune
                return;
            } else if (proofClaim.claimedEpoch != currentEpoch - 1) {
                // If no proof claim is made, prune the pending chain
                _prune();
                return;
            }
        }
    }

    function _prune() internal {
        state.pendingTip = state.provenTip;
        emit PendingChainPruned(state.pendingTip.blockNumber, state.pendingTip.slotNumber);
    }


    function proposeBlock(bytes32 _blockHash, bytes32 _archive) external {
        _pruneIfNeeded();
        // Additional block proposal logic here
        // ...
    }

    function submitProofOfEpoch(bytes calldata _epochHeader) external {
        EpochHeader memory epochHeader = abi.decode(_epochHeader, (EpochHeader));
        uint256 finalBlockNumber = epochHeader.finalBlockNumber;

        uint256 currentEpoch = getCurrentEpoch();

        // We cannot use chain tip and length because the final block in the epoch may not be in the final slot
        ProposalLog memory proposalLog = proposalLogs[finalBlockNumber];
        if (proposalLog.hash == 0) {
            revert Rollup__NoProposalLog();
        }

        ProposalLog memory nextProposalLog = proposalLogs[finalBlockNumber + 1];
        // This serves two checks:
        // 1. The proof is submitted in the correct epoch
        // 2. The proof does not truncate the blocks in the epoch it is proving
        if (nextProposalLog.hash != 0 &&
            getEpochAt(nextProposalLog.slotNumber) != currentEpoch) {
            revert Rollup__NotLastBlockInEpoch();
        }

        bytes32 previousProvenArchive = proposalLogs[state.provenTip.blockNumber].archive;
        // Proof verification logic here, using the previous proven archive
        // which ensure's we aren't omitting an epoch

        state.provenTip = ChainTip(finalBlockNumber, proposalLog.slotNumber);

        for (uint256 i = 0; i < epochHeader.fees.length; i++) {
            Fee memory fee = epochHeader.fees[i];
            if (fee.recipient != address(0)) {
                feeJuicePortal.distributeFees(proofClaim.rewardRecipient, fee.recipient, fee.amount);
            }
        }

        // escrow will check that the amount has actually been staked to this rollup.
        escrow.unstakeBond(proofClaim.bondProvider, proofClaim.bondAmount);
        emit ProofSubmitted(proofClaim.claimedEpoch, finalBlockNumber);
    }

}
```

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [x] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

### Unit tests (solidity)

Claiming proof rights:
- Signature generation
  - can claim iff the proposer in the current slot has signed
- Successful claim by a bond provider
  - In the first/middle/last slot of the claim phase
- Preventing double claims
- Preventing claims outside the claim phase

Chain pruning:
- Pruning when no proof claim is made
  - Pending chain should reset to the proven tip with the current committee
- Pruning when a claim is made but no proof is submitted

Submitting proof of epoch:
- Successful submission of a proof

Testing all the above when:
  - the previous epoch was empty
  - the previous epoch has empty slots (particularly at the beginning/end of an epoch)
  - this is the first epoch

### E2E tests

All existing E2E tests should pass. Additional E2E will be written after the sequencer has been updated to handle reorgs.

## Documentation Plan

TBD

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
