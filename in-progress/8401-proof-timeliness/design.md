# Proof Timeliness

|                      |                                                             |
| -------------------- | ----------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8401 |
| Owners               | @just-mitch                                                 |
| Approvers            | @LHerskind                                                  |
| Target Approval Date | YYYY-MM-DD                                                  |


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

## Rough Implementation

This is a rough, illustrative implementation of the proof timeliness requirement to guide intuition.  
For example, it is highly unlikely that the rollup contract will hold the bond.

The key "trick" is that we prune the pending chain as part of a proposer's block submission.

An observation is that in the current design, the committee does not change in the event that no proof claim is posted for the previous epoch.

```solidity

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
    IERC20 public testToken;
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

    constructor(address _testToken, address _feeJuicePortal) {
        testToken = IERC20(_testToken);
        feeJuicePortal = IFeeJuicePortal(_feeJuicePortal);
    }

    function claimProofRight(address _bondProvider) external {
        uint256 currentSlot = getCurrentSlot();
        address currentProposer = getCurrentProposer();

        if (currentProposer != address(0) && currentProposer != msg.sender) {
            revert Rollup__NonProposerCannotClaimProofRight();
        }

        if (proofClaim.rewardRecipient != address(0)) {
            revert Rollup__ProofRightAlreadyClaimed();
        }

        if (currentSlot % EPOCH_DURATION >= CLAIM_DURATION) {
            revert Rollup__NotInClaimPhase();
        }

        // Bond provider must have approved the contract to transfer the bond amount
        testToken.transferFrom(_bondProvider, address(this), PROOF_COMMITMENT_BOND_AMOUNT);

        proofClaim = ProofClaim({
            rewardRecipient: msg.sender,
            bondProvider: _bondProvider,
            claimedEpoch: getCurrentEpoch() - 1
        });

        emit ProofRightClaimed(msg.sender, proofClaim.claimedEpoch, currentSlot);
    }

    function _prune() internal {
        uint256 currentSlot = getCurrentSlot();
        uint256 currentEpoch = getCurrentEpoch();
        uint256 currentEpochStartSlot = currentEpoch * EPOCH_DURATION;

        if (proofClaim.rewardRecipient == address(0) &&
            currentSlot >= currentEpochStartSlot + CLAIM_DURATION) {
            state.pendingTip = state.provenTip;
            emit PendingChainPruned(state.pendingTip.blockNumber, state.pendingTip.slotNumber);
        } else if (proofClaim.rewardRecipient != address(0) &&
                   currentSlot >= currentEpochStartSlot + EPOCH_DURATION) {
            state.pendingTip = state.provenTip;
            _slashBond();
            emit PendingChainPruned(state.pendingTip.blockNumber, state.pendingTip.slotNumber);
        }
    }


    function proposeBlock(bytes32 _blockHash, bytes32 _archive) external {
        _prune();
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

        _returnBond();
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

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.

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
