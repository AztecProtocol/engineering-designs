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

This phase has a duration of $C$ slots (e.g. 16 slots).

During this time, the proposer for a slot can submit a claim to be the prover for the previous epoch.

This can be a transaction separate from the submission of their proposed block.

Doing so grants monopoly rights to the rewards for submitting the proof of epoch `n-1`.

If no claim is submitted, the pending chain is pruned to the tip of the proven chain.

### Proof production phase

If a claim is submitted during the proof claim phase, the next phase is the "proof production phase".

This phase has a duration of $P$ slots (e.g. 16 slots).

Failure to submit a proof results in the bond posted with the claim being slashed.

Further, the pending chain is pruned to the tip of the proven chain.

The wall time duration of $P$ slots must be greater than the time required to produce a proof.

For simplicity, $P + C <= E$: this means we will never be producing a proof for more than one epoch at a time.

## Implementation

```solidity
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

struct ProofBond {
    address bondProvider;
    address rewardRecipient;
    uint256 slotOfClaim;
}

struct Fee {
    address recipient;
    uint256 amount;
}

struct EpochHeader {
    uint256 finalBlockNumber;
    Fee[32] fees;
}

// State variables
State public state;
mapping(uint256 => ProposalLog) public proposalLogs;
ProofBond public proofBond;
IERC20 public testToken;

// Constants
uint256 public constant CLAIM_DURATION = 16;
uint256 public constant PROOF_DURATION = 16;
uint256 public constant EPOCH_DURATION = 32;
uint256 public constant PROOF_COMMITMENT_BOND_AMOUNT = 100;


function claimProofRight(
  // the proposer may have a deal with a prover marketplace, who will pay the bond
  address _bondProvider,

) external {
  uint256 currentSlot = getCurrentSlot();
  address currentProposer = getCurrentProposer();

  if (currentProposer != address(0) && currentProposer != msg.sender) {
    revert Errors.Rollup__NonProposerCannotClaimProofRight();
  }

  if (proofBond.rewardRecipient != address(0)) {
    revert Errors.Rollup__ProofRightAlreadyClaimed();
  }

  if (currentSlot % EPOCH_DURATION >= CLAIM_DURATION) {
    revert Errors.Rollup__NotInClaimPhase();
  }

  // transfer the bond from the bond provider to the rollup contract
  testToken.transferFrom(_bondProvider, address(this), PROOF_COMMITMENT_BOND_AMOUNT);

  proofBond.rewardRecipient = msg.sender;
  proofBond.bondProvider = _bondProvider;
  proofBond.slotOfClaim = currentSlot;

  // we don't need to store the epoch number, as it can be inferred from the current slot
  claimedEpoch = getCurrentEpoch() - 1;

  emit ProofRightClaimed(msg.sender, claimedEpoch, currentSlot);
}


function _prune() internal {
  uint256 currentSlot = getCurrentSlot();
  uint256 currentEpoch = getCurrentEpoch();
  if (
    // if the proof claim phase has ended
    // and no one has claimed
    currentProofClaimer == address(0) && 
    currentSlot >= state.provenTip.slotNumber + EPOCH_DURATION + CLAIM_DURATION
  ) {
    // prune the pending chain to the tip of the proven chain
    state.pendingTip = state.provenTip;
    emit PendingChainPruned(state.pendingTip.blockNumber, state.pendingTip.slotNumber);
  } else if (
    // if the proof production phase has ended
    // and no proof has been submitted
    currentProofClaimer != address(0) &&
    currentSlot >= proofBond.slotOfClaim + PROOF_DURATION
  ) {
    // prune the pending chain to the tip of the proven chain
    state.pendingTip = state.provenTip;
    _slashBond(); 
    emit PendingChainPruned(state.pendingTip.blockNumber, state.pendingTip.slotNumber);
  }
}

function _slashBond() internal {
  // do nothing at the moment
  // i.e. the rollup contract will keep the bond
  proofBond.rewardRecipient = address(0);
  proofBond.bondProvider = address(0);

  emit BondSlashed();
}

function _returnBond() internal {
  // return the bond to the bond provider
  testToken.transfer(proofBond.bondProvider, PROOF_COMMITMENT_BOND_AMOUNT);
  proofBond.rewardRecipient = address(0);
  proofBond.bondProvider = address(0);

  emit BondReturned();
}

function proposeBlock() {
  // call _prune before proposing a block
  _prune();
  // ...
}

function submitProofOfEpoch(
  // ...other args
  bytes calldata _epochHeader
) {
  EpochHeader memory epochHeader = decodeHeader(_epochHeader);
  uint256 finalBlockNumber = epochHeader.finalBlockNumber;
  Fee[32] memory fees = epochHeader.fees;

  ProposalLog memory proposalLog = proposalLogs[finalBlockNumber];
  if (proposalLog.hash == 0) {
    revert Errors.Rollup__NoProposalLog();
  }

  // check that the proven block is from the previous epoch
  if (
    getEpochAt(proposalLog.slotNumber) != getCurrentEpoch() - 1
  ) {
    revert Errors.Rollup__NotPreviousEpoch();
  }

  // check that the proven block is the last one in the epoch
  ProposalLog memory nextProposalLog = proposalLogs[finalBlockNumber + 1];
  if (
    // if there is a next proposal log
    nextProposalLog.hash != 0 &&
    // and it is in the same epoch
    getEpochAt(nextProposalLog.slotNumber) == getCurrentEpoch() - 1
  ) {
    revert Errors.Rollup__NotLastBlockInEpoch();
  }

  // check that the proof is submitted within the proof production phase
  uint256 currentSlot = getCurrentSlot();
  if (
    currentSlot >= proofBond.slotOfClaim + PROOF_DURATION
  ) {
    revert Errors.Rollup__ProofProductionPhaseEnded();
  }

  // ... go on and verify the proof

  // if the proof is valid
  // update the proven tip
  state.provenTip = ChainTip(provenBlockNumber, proposalLog.slotNumber);

  // for each fee
  for (uint256 i = 0; i < fees.length; i++) {
    if (fees[i].recipient == address(0)) {
      continue;
    }
    FEE_JUICE_PORTAL.distributeFees(
      proofBond.rewardRecipient, // the prover gets some fees
      fees[i].recipient, // as does the proposer
      fees[i].amount
    );
  }

  _returnBond();
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
