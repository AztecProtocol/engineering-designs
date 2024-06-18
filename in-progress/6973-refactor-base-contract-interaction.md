|                      |                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------- |
| Issue                | [Refactor Contract Interactions](https://github.com/AztecProtocol/aztec-packages/issues/6973) |
| Owners               | @just-mitch                                                                                   |
| Approvers            | @PhilWindle @LHerskind                                                                        |
| Target Approval Date | 2024-06-21                                                                                    |


## Executive Summary

This is a refactor of the API for interacting with contracts to improve the user (developer) experience, focused on aztec.js.

The refactored approach mimics Viem's API, with some enhancements and modifications to fit our needs.

In a nutshell, by being more verbose in the API, we can remove a lot of complexity and make the code easier to understand and maintain; this also affords greater understanding and control over the lifecycle of contracts and transactions.

Key changes:
- the wallet is the central point of interaction to simulate/prove/send transactions instead of `BaseContractInteraction`
- unified api for deploying contracts, deploying accounts, and calling functions
- idempotent simulations
- enables more sophisticated gas estimation mechanism

### Major Interface Update

Remove `BaseContractInteraction` and its subclasses.

Define the following:

```ts
export interface UserAPI {
  getTxExecutionRequest(userRequest: UserRequest): Promise<TxExecutionRequest>;
  simulate(userRequest: UserRequest): Promise<SimulationOutput>;
  read(userRequest: UserRequest): Promise<SimulationOutput>;
  prove(userRequest: UserRequest): Promise<UserRequest>;
  send(userRequest: UserRequest): Promise<SentTx>;
}

export type Wallet = UserAPI & AccountInterface & PXE & AccountKeyRotationInterface;
```

### Account Creation

```ts
const pxe = await createCompatibleClient(rpcUrl, debugLogger);
const secretKey = Fr.random();
const salt = 42;

// Returns the wallet and deployment options. 
// Does not modify PXE state.
const { wallet: aliceWallet, deploymentArgs } = await getSchnorrWallet(pxe, secretKey, salt);

const aliceContractInstance = getContractInstanceFromDeployParams(
  SchnorrAccountContract.artifact, 
  deploymentArgs
);

// Register the account in PXE, and wait for it to sync.
await aliceWallet.registerAccountInPXE({ sync: true });

const paymentMethod = new SomeFeePaymentMethod(
  someCoin.address,
  someFPC.address,
  // the fee payment method may need a wallet,
  // e.g. for reading the balance or producing authwits
  aliceWallet
);

// Changes to the PXE (e.g. notes, nullifiers, auth wits, contract deployments, capsules) are not persisted.
const { request: deployAliceAccountRequest } = await aliceWallet.simulate({
  // easy multicall support
  calls: [{
    artifact: SchnorrAccountContract.artifact,
    instance: aliceContractInstance,
    functionName: deploymentArgs.constructorName,
    args: deploymentArgs.constructorArgs,
  }],
  paymentMethod,
  // gasSettings: undefined => automatic gas estimation. the returned `request` will have the gasSettings set.
});

// Wallet can stop here to prompt the user to confirm the gas estimation.

const deployAliceAccountRequestWithProof = await aliceWallet.prove(deployAliceAccountRequest);

const sentTx = await aliceWallet.send(deployAliceAccountRequestWithProof)

const receipt = await sentTx.wait({
  // permanently add the transient contracts to the wallet if the tx is successful.
  // defaults to true.
  registerOnSuccess: true
});


```

### Deploy Token

```ts
const bananaCoinDeploymentArgs: InstanceDeploymentParams = {
  constructorName: 'constructor',
  constructorArgs: {
    admin: aliceWallet.getAddress(),
    name: 'BananaCoin',
    symbol: 'BC',
    decimals: 18
  },
  salt: 43,
  publicKeysHash: Fr.ZERO,
  deployer: aliceWallet.getAddress()
}

const bananaCoinInstance = getContractInstanceFromDeployParams(
  TokenContract.artifact,
  bananaCoinDeploymentArgs
);

const { request: deployTokenRequest } = await aliceWallet.simulate({
  calls: [{
    artifact: TokenContract.artifact,
    instance: bananaCoinInstance,
    functionName: bananaCoinDeploymentArgs.constructorName,
    args: bananaCoinDeploymentArgs.constructorArgs,
    deploymentOptions: {
      registerClass: true,
      publicDeploy: true,
    },
  }],
  paymentMethod
})

const deployTokenRequestWithProof = await aliceWallet.prove(deployTokenRequest);
const sentTx = await aliceWallet.send(deployTokenRequestWithProof)
const receipt = await sentTx.wait()

```

### Use Token

```ts
const { result: privateBalance } = await aliceWallet.read({
  calls: [{
    contractInstance: bananaCoinInstance,
    functionName: 'balance_of_private'
    args: {owner: aliceWallet.getAddress()}
  }]
});


const { request: transferRequest } = await aliceWallet.simulate({
  contractInstance: bananaCoinInstance,
  functionName: 'transfer',
  args: { 
    from: aliceAddress,
    to: bobAddress,
    value: privateBalance,
    nonce: 0n
  },
  paymentMethod,
});

const transferRequestWithProof = await aliceWallet.prove(transferRequest);
const sentTx = await aliceWallet.send(transferRequestWithProof)
const receipt = await sentTx.wait()

```

## Introduction

Developers and users have to think too hard when deploying accounts and submitting transactions.

This is due in part to holding mutable state in the `BaseContractInteraction` class, which is a base class for all contract interactions; it has multiple subclasses that mutate the state, so it is hard to know what has been set.

For example, the current attempt to estimate gas has a section that reads:
```ts
  // REFACTOR: both `this.txRequest = undefined` below are horrible, we should not be caching stuff that doesn't need to be.
  // This also hints at a weird interface for create/request/estimate/send etc.

  // Ensure we don't accidentally use a version of tx request that has estimateGas set to true, leading to an infinite loop.
  this.txRequest = undefined;
  const txRequest = await this.create({
    fee: { paymentMethod, gasSettings: GasSettings.default() },
    estimateGas: false,
  });
  // Ensure we don't accidentally cache a version of tx request that has estimateGas forcefully set to false.
  this.txRequest = undefined;
```

Doing this well also requires that simulations to be idempotent: all changes to the PXE including notes, nullifiers, auth wits, contract deployments, capsules, etc. should not be persisted until the user explicitly sends the transaction.

This would fix comments seen in the `DeployMethod` class like:
```ts
// TODO: Should we add the contracts to the DB here, or once the tx has been sent or mined?
// Note that we need to run this registerContract here so it's available when computeFeeOptionsFromEstimatedGas
// runs, since it needs the contract to have been registered in order to estimate gas for its initialization,
// in case the initializer is public. This hints at the need of having "transient" contracts scoped to a
// simulation, so we can run the simulation with a set of contracts, but only "commit" them to the wallet
// once this tx has gone through.
await this.wallet.registerContract({ artifact: this.artifact, instance: this.getInstance(options) });

// ...

if (options.estimateGas) {
  // Why do we call this seemingly idempotent getter method here, without using its return value?
  // This call pushes a capsule required for contract class registration under the hood. And since
  // capsules are a stack, when we run the simulation for estimating gas, we consume the capsule
  // that was meant for the actual call. So we need to push it again here. Hopefully this design
  // will go away soon.
  await this.getDeploymentFunctionCalls(options);
  request.fee = await this.getFeeOptionsFromEstimatedGas(request);
}
```

We also want to unify the mechanism for creating, simulating, proving, and sending transactions, regardless of whether they are for deploying a contract, calling a function, or deploying an account.

This would clear up concerns like:

> // REFACTOR: Having a `request` method with different semantics than the ones in the other
  // derived ContractInteractions is confusing. We should unify the flow of all ContractInteractions.


## Interface

The key operations we want to perform are:
- Simulating/Reading
- Proving
- Submitting

These operations should be accessible from a `Wallet`, which will generally be `Schnorr` or `Signerless`. 

This is analogous to `viem` having a `walletClient` and a `publicClient`.

The main idea in this design is to have the BaseWallet define all the functionality to perform the key operations; the specific entrypoint in use will be able to adapt the `TxExecutionRequest`s produced to its needs.

To accomplish this, we have the BaseWallet construct a `TxExecutionRequestBuilder` that can be passed to various `TxExecutionRequestAdapters`, such as one for the account entrypoint, one for the fee payment method, etc.

Further, we expand `TxExecutionRequest` to allow passing things that we were previously setting directly on the PXE, so simulations can be idempotent.

The interfaces are as follows:

```ts

// new
export interface ArtifactAndInstance {
  artifact: ContractArtifact;
  instance: ContractInstanceWithAddress;
}

// modified
export class TxExecutionRequest {
  constructor(
    // All these are the same:
    public origin: AztecAddress,
    public functionSelector: FunctionSelector,
    public firstCallArgsHash: Fr,
    public txContext: TxContext,
    public argsOfCalls: PackedValues[],
    public authWitnesses: AuthWitness[],
    // Add:
    /**
     * Transient capsules needed for this execution.
     */
    public capsules: Fr[][],
    /**
     * Transient contracts needed for this execution.
     */
    public transientContracts: ArtifactAndInstance[],
  ) {}
  // ...
}

// new
export interface InstanceDeploymentParams {
  constructorName: string;
  constructorArgs: any;
  salt: Fr;
  publicKeysHash: Fr;
  deployer: AztecAddress;
}

// new
export interface DeploymentOptions {
  registerClass?: boolean;
  publicDeploy?: boolean;
}

export interface UserFunctionCall {
  contractInstance: ContractInstanceWithAddress;
  functionName: string;
  args: any;
  deploymentOptions?: DeploymentOptions;
  contractArtifact?: ContractArtifact;
  functionAbi?: FunctionAbi;
}

// new
export interface UserRequest {
  calls: UserFunctionCall[];
  gasSettings?: GasSettings;
  paymentMethod?: FeePaymentMethod;
  from?: AztecAddress;
  simulatePublicFunctions?: boolean;
  executionResult?: ExecutionResult; // the raw output of a simulation that can be proven
  tx?: Tx; // a proven tx to send
}

export type TxExecutionRequestAdapter = (builder: TxExecutionRequestBuilder, userRequest: UserRequest) => Promise<void>;

export interface TxExecutionRequestComponent {
  adaptTxExecutionRequest: TxExecutionRequestAdapter;
}

export interface FeePaymentMethod extends TxExecutionRequestComponent {
  getEquivalentAztBalance(): Promise<Fr>;
}

export interface SimulationOutput {
  tx: Tx;
  result: DecodedReturn | [];
  request: UserRequest;
  executionResult: ExecutionResult;
  publicOutput: PublicSimulationOutput;
  privateOutput: NestedProcessReturnValues;
  error?: SimulationError;
}

export interface UserAPI {
  getTxExecutionRequest(userRequest: UserRequest): Promise<TxExecutionRequest>;
  simulate(userRequest: UserRequest): Promise<SimulationOutput>;
  read(userRequest: UserRequest): Promise<SimulationOutput>;
  prove(userRequest: UserRequest): Promise<UserRequest>;
  send(userRequest: UserRequest): Promise<SentTx>;
}

export type Wallet = UserAPI & AccountInterface & PXE & AccountKeyRotationInterface;

// Swap `EntrypointInterface` for `TxExecutionRequestComponent`
export interface AccountInterface extends AuthWitnessProvider, TxExecutionRequestComponent {
  getCompleteAddress(): CompleteAddress;
  getAddress(): AztecAddress;
  getChainId(): Fr;
  getVersion(): Fr;

}

// unchanged
export interface AuthWitnessProvider {
  createAuthWit(
    messageHashOrIntent:
      | Fr
      | Buffer
      | {
          caller: AztecAddress;
          action: ContractFunctionInteraction | FunctionCall;
          chainId?: Fr;
          version?: Fr;
        },
  ): Promise<AuthWitness>;
}

```


## Implementation

### Expose an explicit `proveTx` on PXE

We currently don't have a way to *only* prove a transaction; everything must be simulated first.

So we will expose a `proveTx` method on the PXE that will take a `TxExecutionRequest` and an `ExecutionResult` and return a `Tx`.

### Drop `isFeePayer` from `FeeEntrypointPayload`


Removing this makes the code simpler and more flexible: account contracts can just check if fee payer has been set and set it if not.

Concerned users can just inspect the simulation result to see if they are paying the fee.

Then we just have `EntrypointPayload` as a single, concrete class.

### BaseWallet.getTxExecutionRequest

Consider that we have, e.g.:

```ts
{
  calls: [{
    contractInstance: bananaCoinInstance,
    functionName: 'transfer',
    args: { 
      from: aliceAddress,
      to: bobAddress,
      value: privateBalance,
      nonce: 0n
    },
  }],
  paymentMethod
}
```

We need to ultimately get to a `TxExecutionRequest`.

#### Translate a `contractInstance`, `functionName` and `args` to a `FunctionCall`

Define helpers somewhere as:

```ts

function findFunctionAbi(contractArtifact: ContractArtifact, functionName: string): FunctionAbi {
  const functionAbi = contractArtifact.abi.find((abi) => abi.name === functionName);
  if (!functionAbi) {
    throw new Error(`Function ${functionName} not found in contract artifact`);
  }
  return functionAbi;
}

function makeFunctionCall(
  functionAbi: FunctionAbi,
  instanceAddress: AztecAddress,
  args: any,
): FunctionCall {
  return FunctionCall.from({
    name: functionAbi.name,
    args: mapArgsObjectToArray(functionAbi.parameters, args),
    selector: FunctionSelector.fromNameAndParameters(functionAbi.name, functionAbi.parameters),
    type: functionAbi.functionType,
    to: instanceAddress,
    isStatic: functionAbi.isStatic,
    returnTypes: functionAbi.returnTypes,
  });
}

```

#### main function calls

Define a helper somewhere as:

```ts
const addMainFunctionCall: TxExecutionRequestAdapter = (
  builder: TxExecutionRequestBuilder, call: UserFunctionCall
) => {
  if (!call.functionAbi) {
    throw new Error('Function ABI must be provided');
  }
  builder.addAppFunctionCall(
    makeFunctionCall(
      call.functionAbi,
      call.contractInstance.address,
      call.args
  ));
}
```

#### class registration

Define a helper somewhere as:

```ts
const addContractClassRegistration = (
  builder: TxExecutionRequestBuilder, call: UserFunctionCall
) => {
  if (!call.contractArtifact) {
    throw new Error('Contract artifact must be provided to register class');
  }

  const contractClass = getContractClassFromArtifact(call.contractArtifact);

  builder.addCapsule(
    bufferAsFields(
      contractClass.packedBytecode,
      MAX_PACKED_PUBLIC_BYTECODE_SIZE_IN_FIELDS
  ));

  const { artifact, instance } = getCanonicalClassRegisterer();

  const registerFnAbi = findFunctionAbi(artifact, 'register');

  builder.addAppFunctionCall(
    makeFunctionCall(
      registerFnAbi,
      instance.address,
      {
        artifact_hash: contractClass.artifactHash,
        private_functions_root: contractClass.privateFunctionsRoot,
        public_bytecode_commitment: contractClass.publicBytecodeCommitment
      }
  ));
}
```

#### public deployment

Define a helper somewhere as

```ts

const addPublicContractDeployment = (
  builder: TxExecutionRequestBuilder, call: UserFunctionCall
) => {
  const { artifact, instance } = getCanonicalInstanceDeployer();
  const deployFnAbi = findFunctionAbi(artifact, 'deploy');
  builder.addAppFunctionCall(
    makeFunctionCall(
      deployFnAbi,
      instance.address,
      {
        salt: request.contractInstance.salt,
        contract_class_id: request.contractInstance.contractClassId,
        initialization_hash: request.contractInstance.initializationHash,
        public_keys_hash: request.contractInstance.publicKeysHash,
        universal_deploy: request.contractInstance.deployer.isZero(),
      }
  ));
}

```

#### Entrypoints implement `TxExecutionRequestComponent`

Below is what a default account entrypoint might look like, but other entrypoints could implement this differently

```ts

export class DefaultAccountEntrypoint implements TxExecutionRequestComponent {
  constructor(
    private address: AztecAddress,
    private auth: AuthWitnessProvider,
    private chainId: number = DEFAULT_CHAIN_ID,
    private version: number = DEFAULT_VERSION,
  ) {}

  async adaptTxExecutionRequest(
    builder: TxExecutionRequestBuilder,
    userRequest: UserRequest
  ): Promise<void> {
    const appPayload = EntrypointPayload.fromFunctionCalls(builder.appFunctionCalls);
    const setupPayload = EntrypointPayload.fromFunctionCalls(builder.setupFunctionCalls);
    const abi = this.getEntrypointAbi();
    const entrypointPackedArgs = PackedValues.fromValues(encodeArguments(abi, [appPayload, setupPayload]));

    return builder
      .setOrigin(this.address)
      .setTxContext({
        chainId: this.chainId,
        version: this.version,
        gasSettings: userRequest.gasSettings,
      })
      .setFunctionSelector(
        FunctionSelector.fromNameAndParameters(abi.name, abi.parameters)
      )
      .setFirstCallArgsHash(entrypointPackedArgs.hash());
      .setArgsOfCalls([
        ...appPayload.packedArguments,
        ...feePayload.packedArguments,
         entrypointPackedArgs
      ])
      .addAuthWitness(
        await this.auth.createAuthWit(appPayload.hash())
      )
      .addAuthWitness(
        await this.auth.createAuthWit(setupPayload.hash())
      )
  }

  private getEntrypointAbi() {
    return {
      name: 'entrypoint',
      isInitializer: false,
      // ... same as before
    }
  }
}

```

#### Fill in the `TxExecutionRequest`

The abstract `BaseWallet` can implement:

```ts
async getTxExecutionRequest(userRequest: UserRequest): Promise<TxExecutionRequest> {
  if (!userRequest.gasSettings) {
    throw new Error('Gas settings must be provided');
  }
  if (!userRequest.paymentMethod) {
    throw new Error('Payment method must be provided');
  }

  const builder = new TxExecutionRequestBuilder();

  for (const call of request.calls) {
    addMainFunctionCall(builder, call);
    if (call.deploymentOptions?.registerClass) {
      addContractClassRegistration(builder, call);
    }
    if (call.deploymentOptions?.publicDeploy) {
      addPublicContractDeployment(builder, call);
    }
    // if the user is giving us an artifact,
    // allow the PXE to access it
    if (call.contractArtifact) {
      builder.addTransientContract({
        artifact: call.contractArtifact,
        instance: call.contractInstance,
      });
    }
  }

  // Add stuff needed for setup, e.g. function calls, auth witnesses, etc.
  await userRequest.paymentMethod.adaptTxExecutionRequest(builder, userRequest);

  // Adapt the request to the entrypoint in use.
  // Since BaseWallet is abstract, this will be implemented by the concrete class.
  this.adaptTxExecutionRequest(builder, userRequest);

  return builder.build();

}
```

### BaseWallet.#simulateInner

```ts
// Used by simulate and read
async #simulateInner(userRequest: UserRequest): ReturnType<BaseWallet['simulate']> {
  const txExecutionRequest = await this.getTxExecutionRequest(userRequest);
  const simulatedTx = await this.simulateTx(txExecutionRequest, builder.simulatePublicFunctions, builder.from); 
  const decodedReturn = decodeSimulatedTx(simulatedTx, builder.functionAbi);
  return {
    tx: simulatedTx.tx,
    publicOutput: simulatedTx.publicOutput,
    privateOutput: simulatedTx.privateReturnValues,
    executionResult: simulatedTx.executionResult,
    result: decodedReturn,
    request: userRequest,
  };
}
```

### BaseWallet.simulate

```ts

async simulate(userRequest: UserRequest): {
    tx: simulatedTx.tx,
    publicOutput: simulatedTx.publicOutput,
    privateOutput: simulatedTx.privateReturnValues,
    executionResult: simulatedTx.executionResult,
    result: decodedReturn,
    request: initRequest,
} {
  // If we're simulating, we need to have the payment method set.
  // Users should use `read` if they just want to see the result.
  if (!userRequest.paymentMethod){
    throw new Error('Payment method must be set before simulating');
  }

  const builder = new UserRequestBuilder(userRequest);

  await this.#ensureFunctionAbis(builder);

  if (builder.gasSettings) {
    return this.#simulateInner(builder.build());
  }

  // If we're paying, e.g. in bananas, figure out how much AZT that is.
  // Note: paymentMethod.getEquivalentAztBalance() may call `read` internally.
  const equivalentAztBalance = await builder.paymentMethod.getEquivalentAztBalance();
  gasEstimator = new BinarySearchGasEstimator(equivalentAztBalance);
  builder.setGasSettings(gasEstimator.proposeGasSettings());

  while (!gasEstimator.isConverged()) {
    const result = await this.#simulateInner(builder.build());
    gasEstimator.update(result);
    builder.setGasSettings(gasEstimator.proposeGasSettings());
  }

  return result;
}

async #ensureFunctionAbis(builder: UserRequestBuilder): void {
  for (const call of builder.calls) {
    // User can call simulate without the artifact if they have the function ABI
    if (!call.functionAbi) {
      // If the user provides the contract artifact, we don't need to ask the PXE
      if (!call.contractArtifact) {
        const contractArtifact = await this.getContractArtifact(call.contractInstance.contractClassId);
        call.setContractArtifact(contractArtifact);
      }
      const functionAbi = findFunctionAbi(call.contractArtifact, call.functionName);
      call.setFunctionAbi(functionAbi);
    }
  }
}

// helpers somewhere

function decodeSimulatedTx(simulatedTx: SimulatedTx, functionAbi: FunctionAbi): DecodedReturn | [] {
  const rawReturnValues =
    functionAbi.functionType == FunctionType.PRIVATE
      ? simulatedTx.privateReturnValues?.nested?.[0].values
      : simulatedTx.publicOutput?.publicReturnValues?.[0].values;

  return rawReturnValues ? decodeReturnValues(functionAbi.returnTypes, rawReturnValues) : [];
}
```

### BaseWallet.read

Like `simulate`, but without the gas estimation.

```ts
async read(userRequest: UserRequest): DecodedReturn | [] {
  const builder = new UserRequestBuilder(userRequest);


  if (!builder.paymentMethod) {
    builder.setFeePaymentMethod(new NoFeePaymentMethod());
  }

  if (!builder.gasSettings) {
    builder.setGasSettings(GasSettings.default());
  }

  await this.#ensureFunctionAbis(builder);

  return this.#simulateInner(builder.build());
}
```


### BaseWallet.prove

```ts
async prove(request: UserRequest): Promise<UserRequest> {
  if (!request.executionResult) {
    throw new Error('Execution result must be set before proving');
  }
  const builder = new UserRequestBuilder(request);
  await this.#ensureFunctionAbis(builder);
  const initRequest = builder.build();
  const txExecutionRequest = await this.getTxExecutionRequest(initRequest);
  const provenTx = await this.proveTx(txExecutionRequest, request.executionResult);
  builder.setTx(provenTx);
  return builder.build();
}
```

### BaseWallet.send

```ts
async send(request: UserRequest): Promise<UserRequest> {
  if (!request.tx) {
    throw new Error('Tx must be set before sending');
  }
  if (!request.tx.proof || request.tx.proof.isEmpty()) {
    throw new Error('Tx must be proven before sending');
  }
  const builder = new UserRequestBuilder(request);
  await this.#ensureFunctionAbis(builder);
  const initRequest = builder.build();
  const txExecutionRequest = await this.getTxExecutionRequest();
  const txHash = await this.sendTx(txExecutionRequest, request.tx);
  return new SentTx(this.pxe, txHash, txExecutionRequest);
}
```

### Dapp Funded Transactions


#### A `TxExecutionRequestComponent` for the Dapp

```ts
export class DefaultDappInterface implements AccountInterface {
  constructor(
    private completeAddress: CompleteAddress,
    private userAuthWitnessProvider: AuthWitnessProvider,
    private dappEntrypointAddress: AztecAddress,
    private chainId: number = DEFAULT_CHAIN_ID,
    private version: number = DEFAULT_VERSION,
  ) {}

  async adaptTxExecutionRequest(
    builder: TxExecutionRequestBuilder,
    userRequest: UserRequest
  ): Promise<void> {
    if (builder.appFunctionCalls.length !== 1) {
      throw new Error(`Expected exactly 1 function call, got ${calls.length}`);
    }
    if (builder.setupFunctionCalls.length !== 0) {
      throw new Error(`Expected exactly 0 setup function calls, got ${calls.length}`);
    }
    const payload = EntrypointPayload.fromFunctionCalls(builder.appFunctionCalls);
    const abi = this.getEntrypointAbi();

    const entrypointPackedArgs = PackedValues.fromValues(encodeArguments(abi, [payload, this.completeAddress.address]));
    const functionSelector = FunctionSelector.fromNameAndParameters(abi.name, abi.parameters);

    const innerHash = computeInnerAuthWitHash([Fr.ZERO, functionSelector.toField(), entrypointPackedArgs.hash]);
    const outerHash = computeOuterAuthWitHash(
      this.dappEntrypointAddress,
      new Fr(this.chainId),
      new Fr(this.version),
      innerHash,
    );
    const authWitness = await this.userAuthWitnessProvider.createAuthWit(outerHash);

    builder
      .setOrigin(this.dappEntrypointAddress)
      .setTxContext({
        chainId: this.chainId,
        version: this.version,
        gasSettings: userRequest.gasSettings,
      })
      .setFunctionSelector(functionSelector)
      .setFirstCallArgsHash(entrypointPackedArgs.hash)
      .setArgsOfCalls([...payload.packedArguments, entrypointPackedArgs])
      .addAuthWitness(authWitness);

  }


  createAuthWit(messageHash: Fr): Promise<AuthWitness> {
    return this.authWitnessProvider.createAuthWit(messageHash);
  }

  getCompleteAddress(): CompleteAddress {
    return this.completeAddress;
  }

  getAddress(): AztecAddress {
    return this.completeAddress.address;
  }

  getChainId(): Fr {
    return this.chainId;
  }

  getVersion(): Fr {
    return this.version;
  }

  private getEntrypointAbi() {
    return {
      name: 'entrypoint',
      // ... same as before
    }
  }

}
```

#### Create the wallet as normal

```ts
export async function getDappWallet(
  pxe: PXE,
  accountAddress: AztecAddress,
  dappAddress: AztecAddress,
  userAuthWitnessProvider: AuthWitnessProvider,
): Promise<AccountWallet> {
  const completeAddress = await pxe.getRegisteredAccount(accountAddress);
  if (!completeAddress) {
    throw new Error(`Account ${address} not found`);
  }
  const nodeInfo = await pxe.getNodeInfo();
  const entrypoint = new DefaultDappInterface(completeAddress, userAuthWitnessProvider, dappAddress);
  return new AccountWallet(pxe, entrypoint);
}


const schnorr = new SchnorrAccountContract(signingPrivateKey);
const authWitProvider = schnorr.getAuthWitnessProvider();
const aliceDappWrappedWallet = await getDappWallet(pxe, aliceAddress, dappAddress, userAuthWitnessProvider);

const { request: deployAliceAccountRequest } = await aliceDappWrappedWallet.simulate({
  calls: [{
    contractInstance: bananaCoinInstance,
    functionName: 'transfer',
    args: { 
      from: aliceAddress,
      to: bobAddress,
      value: privateBalance,
      nonce: 0n
    },
  }],
  paymentMethod: new NoFeePaymentMethod(),
})

```


### Gas Estimation

```ts


export interface GasEstimator {
  proposeGasSettings(): GasSettings;
  isConverged(): boolean;
  update(simulationOutput: SimulationOutput): void;
}

interface SearchRatios {
  daToL2: number;
  daTearDown: number;
  l2TearDown: number;
}

// Finds a balance that is enough to cover the gas costs of the simulation.
// Marks as converged if the simulation did not run out of gas,
// or if it is not possible to increase the balance further.
export class BinarySearchGasEstimator implements GasEstimator {
  // keep the initial balance
  // and the ratios of daGas to l2Gas
  // as well as the ratios to teardownGas
  private balance: number

  // The upper and lower bounds of the search space.
  // We start at the midpoint of these bounds.
  // The search space is the balance, and the ratios of daGas to l2Gas
  // as well as the ratios to teardownGas.
  // The goal is to find a balance that is enough to cover the gas costs of the simulation.
  // Then we can just use the true gas costs for the actual transaction.
  private upperBounds: SearchRatios;
  private lowerBounds: SearchRatios;
  private current: SearchRatios;
  private mostRecentSimulation?: SimulationOutput;
  private iterations: number = 0;
  private maxIterations: number = 10;
  private epsilon: number = 0.01;



  constructor(private balance: number) {
    this.lowerBounds = {
      daToL2: 0,
      daTearDown: 0,
      l2TearDown: 0,
    };
    this.upperBounds = {
      daToL2: 1,
      daTearDown: 1,
      l2TearDown: 1,
    };
    this.current = {
      daToL2: .5,
      daTearDown: .1,
      l2TearDown: .1,
    };
  }

  update(simulationOutput: SimulationOutput): void {
    // If the simulation ran out of DA gas
    const oog = simulationOutput.getOutOfGas();
    if (!oog) {
      return
    } else if (oog === 'da') {
      // increase the balance
      this.lowerBounds.daToL2 = this.current.daToL2;
    } else if (oog === 'l2') {
      // increase the balance
      this.lowerBounds.daToL2 = this.current.daToL2;
    } else if (oog === 'da_teardown') {
      // increase the balance
      this.lowerBounds.daTearDown = this.current.daTearDown;
    } else if (oog === 'l2_teardown') {
      // increase the balance
      this.lowerBounds.l2TearDown = this.current.l2TearDown;
    }
    // update the current balance
    this.current.daToL2 = (this.lowerBounds.daToL2 + this.upperBounds.daToL2) / 2;
    this.current.daTearDown = (this.lowerBounds.daTearDown + this.upperBounds.daTearDown) / 2;
    this.current.l2TearDown = (this.lowerBounds.l2TearDown + this.upperBounds.l2TearDown) / 2;
  }

  proposeGasSettings(): GasSettings {
    return GasSettings.from({
      gasLimits: {
        daGas: this.balance * this.current.daToL2,
        l2Gas: this.balance * (1-this.current.daToL2),
      },
      teardownGasLimits: {
        daGas: this.balance * this.current.daToL2 * this.current.daTearDown,
        l2Gas: this.balance * (1 - this.current.daToL2) * this.current.l2TearDown,
      },
      // This should actually be informed somehow
      maxFeesPerGas: { daGas: 1, l2Gas: 1 },
      inclusionFee: 0
    });
  }

// 
  isConverged(): boolean {
    // If the simulation did not run out of gas, we are converged.
    if (!this.mostRecentSimulation?.getOutOfGas()) {
      return true;
    }

    // If we have reached the maximum number of iterations, we are converged.
    if (this.iterations >= this.maxIterations) {
      return true;
    }

    // If the search space is too small, we are converged.
    if (this.upperBounds.daToL2 - this.lowerBounds.daToL2 < this.epsilon) {
      return true;
    }
    if (this.upperBounds.daTearDown - this.lowerBounds.daTearDown < this.epsilon) {
      return true;
    }
    if (this.upperBounds.l2TearDown - this.lowerBounds.l2TearDown < this.epsilon) {
      return true;
    }

    return false;

  }

}

```

### Concerns

#### `UserRequest` is a kitchen sink

The `UserRequest` object is a bit of a kitchen sink. It might be better to have a `DeployRequest`, `CallRequest`, etc. that extends `UserRequest`.

Downside here is that the "pipeline" it goes through would be less clear, and components would have to be more aware of the type of request they are dealing with.

#### Just shifting the mutable subclass problem

Arguably the builder + adapter pattern just shifts the "mutable subclass" problem around. I think that since the entire lifecycle of the builder is contained to the `getTxExecutionRequest` method within a single abstract class, it's not nearly as bad as the current situation.

#### Verbosity + loss of convenience

People might be concerned that we lose the ability to do:
```ts
const bananaCoin = await BananaCoin.at(bananaCoinAddress, this.aliceWallet);
bananaCoin.methods.mint_public(this.aliceAddress, this.ALICE_INITIAL_BANANAS).send().wait()
```

I think this is a good thing. It's not clear what `mint_public` does (which is create a stateful `ContractFunctionInteraction`), and it's not clear what `send().wait()` does. It's not even clear what `at` does (which asks the PXE for the underlying instance at the provided address). It's also hard to specify gas settings and payment methods: they're presently pushed into `send`, which doesn't make sense because they're needed for the simulation.

I think we can still have a `BananaCoin` class that wraps the `UserAPI` and provides a more user-friendly interface, but it should be explicit about what it's doing.

I'd suggest we do that in a follow-up design.


## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] L1 Contracts
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] Aztec.nr
- [x] Aztec.js
- [ ] Noir
- [ ] AVM
- [x] Sequencer
- [x] Fees
- [ ] P2P Network
- [ ] Cryptography
- [ ] DevOps

## Test Plan

Implement the above changes and get all the tests to pass.

## Documentation Plan

An enormous amount of documentation will need to be updated. Will likely need to ask DevRel for help.

## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.
