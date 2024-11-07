# Staking

## Requirements

1. Validators MUST stake to join the validator set. 
2. Validators MUST be able to vote on a governance proposal at the Governance Contract to deploy a new rollup and still be able to migrate stake *before* the new Rollup becomes "canonical". 
3. Staked validators MUST be able to specify their rewards address which could be different from their withdrawal address. 
4. Staked validators MUST be able to migrate stake in one transaction. 
5. The new validator set that chooses to migrate should still be able to slash any validators who chose not to move along. This should remain possible for some amount of time AFTER the activation of the new rollup. 

Validators stake with a `Deposit` contract in order to join the validator set. This `Deposit` contract can be thought of as an auxillary sidecar that Rollup instances could choose to use for stake management. 

If a Rollup is using the `Deposit` contract, validators do NOT stake with the Rollup contract directly. This is meant to simplify moving stake during/after a governance upgrade. 

### Deposit Contract

The Deposit contract is an immutable contract living on L1, that is owned by the Governance Contract (i.e. Apella). It implements the following simplified interface:

```solidity

interface IDeposit {
  function deposit(address validatorAddress, address withdrawalAddress, address rewardsAddress, uint256 amountToDeposit, bool followRegistryBool, address rollupAddress) external returns(bool);
  function activateValidator(address rollupAddress, address validatorAddress, uint256 amount);
  function editDeposits(address rollupAddress, address withdrawalAddress, address rewardAddress, address followsRegistryBool):
  function widthdraw(address rollupAddress, address validatorAddress) external returns(bool);
  function unstakeValidators(addresss rollupAddress, address validatorAddress) external returns(bool);
  function slashValidator(address rollupAddress, address validatorAddress) external returns(bool);
}
```

### Deposit Function

* Validators must deposit at least `MIN_DEPOSIT_AMOUNT`. This is the minimum amount you need to deposit to create a new entry in the `Deposits` mapping.  It is completely separate from what Rollup instances dictate to be the minimum staking requirement to join their validator sets. 
* Calling the deposit function should create an entry in the `Deposits` mapping. This mapping is a `mapping(address rollupAddress => mapping(address validatorAddress => DepositLib.DepositObject))`
* A `DepositObject` contains references to the `withdrawalAddress` , `rewardsAddress` and `followingRegistryBool` variables. It is unique per rollupAddress / validatorAddress combination. 
* Therefore validators can have multiple deposits corresponding to different Rollups. But for each Rollup, they can only have one deposited balance, one `withdrawalAddrss` one `rewardsAddress` and one `followingRegistryBool` flag. 

```python
## High level psuedocode for deposit()
function deposit(validatorAddress, withdrawalAddress, rewardsAddress, amountToDeposit, followRegistryBool, rollupAddress):
    # Step 1: Check minimum deposit requirement
    if amountToDeposit < MIN_DEPOSIT_AMOUNT:
        return False  # or throw an error indicating insufficient deposit amount

    # Step 2: Check if a DepositObject already exists for this rollup and validator address
    if Deposits[rollupAddress][validatorAddress] exists:
        # Add the deposited amount to the existing DepositObject
        Deposits[rollupAddress][validatorAddress].balance += amountToDeposit
    else:
        # Step 3: If no deposit exists, create a new DepositObject
        newDeposit = DepositLib.DepositObject(
            withdrawalAddress=withdrawalAddress,
            rewardsAddress=rewardsAddress,
            balance=amountToDeposit,
            followRegistryBool=followRegistryBool
        )

        # Step 4: Store the new DepositObject in the Deposits mapping
        Deposits[rollupAddress][validatorAddress] = newDeposit

    # Step 5: Emit a Deposit event to record the deposit action
    emit Deposit(validatorAddress, rollupAddress, amountToDeposit)

    return True
```
>Note: Sorry I seem to have made up my own language. It's on you @LHerskind

### Entering the Validator Set

* A Rollup instance can add validators to its validator set by calling `activateValidator`. 
* Any amounts specified by `activateValidator` are removed from `Deposits` and accounted for in a different mapping, `StakedDeposits` which is the same mapping as `Deposits`. 
* Balances held in `StakedDeposits` are subject to slashing.

```python
function activateValidator(rollupAddress, validatorAddress, amount):
    ## If rollupAddress != address(0) then this is attempting to migrate stake. 
    if rollupAddress != address(0):
        if Deposits[rollupAddress][validatorAddress] does not exist:
            return false # Validator has never deposited to rollupAddress
    # If this validator already has a staked deposit entry
        if StakedDeposits[rollupAddress][validatorAddress] does not exist:
            return False
        ## Validator is not following along with governance, must first unstake then manually migrate
        if StakedDeposits[rollupAddress][validatorAddress].followRegistryBool != true:
            return False
        ## Make sure msg.sender is the current canonical rollup. 
        newRollup = this.getRollup()
        require(msg.sender == newRollup)
        require(amount <= StakedDeposits[rollupAddress][validatorAddress].balance)
        ## Move over stake
        StakedDeposits[rollupAddress][validatorAddress].balance -= amount
        ## Create new StakedDeposit object
        oldStakedDeposit = StakedDeposits[rollupAddress][validatorAddress]
        newStakedDeposit = new DepositLib.StakedDeposit(
            withdrawalAddress = oldStakedDeposit.withdrawalAddress,
            rewardsAddress=oldStakedDeposit.rewardsAddress,
            balance=amount,
            followRegistryBool=oldStakedDeposit.followRegistryBool
        )
        StakedDeposits[newRollup][validatorAddress] = newStakedDeposit
        ## Notify old Rollup that validator's new balance is StakedDeposits[rollupAddress][validatorAddress].balance
        ## ...
        return True
    ## rollupAddress == address(0)
    if Deposits[msg.sender][validatorAddress] does not exist:
        return False
    else:
        require(amount <= Deposits[msg.sender][validatorAddress].balance)
        ## Reduce balance
        Deposits[msg.sender][validatorAddress].balance -= amount
        newStakedDeposit = DepositLib.StakedObject(
            withdrawalAddress = Deposits[msg.sender][validatorAddress].withdrawalAddress,
            rewardsAddress=Deposits[msg.sender][validatorAddress].rewardsAddress,
            balance=amount,
            followRegistryBool=Deposits[msg.sender][validatorAddress].followRegistryBool
        )
```
>Note: The code sucks but it showcases the requirements. A validator migrates stake from one rollup to another by calling one function on the Rollup contract which in turn calls `activateValidator()`.

### StakedDeposits vs Deposits mappings

* `StakedDeposits` has the same mapping structure as `Deposits`. 
* Validators can alter values of their entries in the `Deposits` mapping. They can change `followRegistryBool` or `rewardsAddress` but they cannot change `withdrawalAddress`. To change `withdrawalAddress` they must first withdraw then re-deposit. 
* Staked validators cannot alter values of their entries in the `StakedDeposits` mapping. They must first unstake and re-deposit. 
* Rollup contracts can reduce / increase balance of staked validators inside `StakedDeposits` but cannot alter values such as `followingRegistryBool`, `withdrawalAddress` or `rewardsAddress`. 

### withdraw and unstakeValidator functions

* Validators can call the withdraw function at any time to remove any balance they have in `Deposits` using `withdraw()`.
* Only the Rollup contract may withdraw balances from `stakedDeposits` using the function `unstakeValidator()`.

```python
## Change values of a DepositObject
function editDeposits(rollupAddress, rewardAddress, followsRegistryBool):
    if Deposits[rollupAddress][msg.sender] does not exist:
        return False
    else:
        Deposits[rollupAddress][msg.sender].rewardsAddress = rewardsAddress
        Deposits[rollupAddress][msg.sender].followsRegistryBool = followsRegistryBool
## Withdraws from Deposits
function withdraw(rollupAddress, amount):
    if Deposits[rollupAddress][msg.sender] does not exist:
        return False
    
    require(amount <= Deposits[rollupAddress][msg.sender].balance)
    Deposits[rollupAddress][msg.sender].balance -= amount
    ## Transfer asset to msg.sender
    ## ...

## Rollup withdraws from StakedObjects
function unstakeValidators(validatorAddress, amount):
    if StakedDeposits[msg.sender][validatorAddress] does not exist:
        return False
    
    require(amount <= StakedDeposits[msg.sender][validatorAddress].balance)
    StakedDeposits[msg.sender][validatorAddress].balance -= amount
    ## Transfer asset to withdrawalAddress
    ## ...
```

Each Rollup implements its own logic for how validators join and exit the validator set. I expect standard delays (i.e. 10 epochs) before a validator  joins the set and longer withdraw delays for PoG-slashing Rollups. 

### Migrating Validator Stake - Rollup Upgrade

Validators join the validator set of the newly deployed Rollup which calls `activateValidator()` on the Deposit contract. This flow is as described above in the pseudocode of `activateValidator()`. 

### Migrating Validator Stake - State Migration

Validators join the validator set of the newly deployed Rollup which calls `activateValidator()` on the Deposit contract. This flow is as described above in the pseudocode of `activateValidator()`. 

Thus no new `Deposit` contracts need to be deployed in the state migration case. 

### Upgrading to a Rollup that does not utilize the Deposit contract

If the new Rollup is not aware of the `Deposit` contract (or does not use one), validators must unstake and withdraw from the old Rollup and deposit in the new Rolllup. 

### Rewards

Any block rewards accruing to validators should be sent to the `rewardsAddress` specified in `StakedDeposits`.
