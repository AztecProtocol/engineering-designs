# Configurable k8s clusters for testing and deploying networks

|                      |                                                             |
| -------------------- | ----------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/7588 |
| Owners               | @just-mitch                                                 |
| Approvers            | @PhilWindle @alexghr @charlielye                            |
| Target Approval Date | 2024-08-16                                                  |


## Executive Summary

We will:
- add a helm chart for deploying a configurable network.
- add support for ad-hoc k8s clusters in CI and running e2e tests on them
- add support for deploying a public network


## Introduction

To properly test a decentralized system, we need the ability to spin up networks with different topologies such as the number of nodes, validators, provers, pxes.

Additionally, we need to test under simulated stress/attack conditions.

Further, we need to be able to deploy these networks in a repeatable and automated way.

> Kubernetes, also known as K8s, is an open source system for automating deployment, scaling, and management of containerized applications.

And [Helm](https://helm.sh/) is "the package manager for Kubernetes".

This allows us to define a network configuration in a helm chart and deploy it to a k8s cluster, setting variables on the fly such as the number of nodes, validators, machine resources, etc.

K8s is also easy to use in CI via [kind](https://kind.sigs.k8s.io/).

> kind is a tool for running local Kubernetes clusters using Docker container “nodes”.
> kind was primarily designed for testing Kubernetes itself, but may be used for local development or CI.

Further, we can use [chaos mesh](https://chaos-mesh.org/) to simulate network conditions such as node failures, latency, etc.

Last, we can likely use the exact same chart to deploy a public network.

### Why not docker compose?

We use docker-compose already in some tests. The problem is that it is very difficult to test a network with more than a few nodes. It is also difficult to simulate network conditions. Last, we wouldn't be able to use the same tooling to deploy a public network.

The thinking here is to use the same tooling that we use for production deployments to test our networks. This should result in less code and more confidence.

## Interface

The users of this work are developers of aztec and possibly infrastructure providers.

There will be a new top-level folder `helm-charts`. In it, there will be a `aztec-network` chart.

A lot of the value is shown in the helm chart's values.yaml file. The values in this file are used to populate the templates that make up the rest of the chart. Here is an example:

```yaml
images:
  aztec:
    image: aztecprotocol/aztec:c07d910d0b8b83b62008e79a7085db6c5020df4e

bootNode:
  replicas: 1
  service:
    p2pPort: 40400
    nodePort: 8080
  logLevel: 'debug'
  debug: 'discv5:*,aztec:*'
  fakeProofs: false
  resources:
    requests:
      cpu: 100m
      memory: 128Gi
    limits:
      cpu: 100m
      memory: 128Gi


validator:
  replicas: 32
  service:
    p2pPort: 40400
    nodePort: 8080
  logLevel: 'debug'
  debug: 'discv5:*,aztec:*'
  fakeProofs: false
  resources: {}

pxe:
  replicas: 3
  service:
    type: ClusterIP
    port: 8080
    targetPort: 8080
  fakeProofs: false
  resources: {}

chaos:
  scenarios:
    - name: 'boot-node-failure'
      type: 'pod'
      selector:
        matchLabels:
          app: boot-node
      action: 'kill'
      actionOptions:
        force: true
```

The `yarn-projects/+end-to-end-base` earthly image will be updated to include `kubectl`, `helm`, and `kind`.

We will add new tests to `yarn-projects/end-to-end`, and expose them to CI as earthly targets in the form `yarn-projects/end-to-end/+network-{test_name}`.

The `ci` github action workflow will have a new job analogous to `e2e` and `bench-e2e` called `network-e2e`. This job will be a matrix on the `+network` targets, and for each it will ensure the test machine has a k8s cluster running with the relevant docker images loaded (via kind), and run a particular earthly target.

Each target will:
1. deploy a network to the k8s cluster (via helm install)
2. (optional) apply some chaos configurations
3. run helm tests
4. tear down the network


## Implementation

### Helm Chart

**anvil**

There will be a deployment for anvil. It will have a single replica, and be exposed via ClusterIP.

**boot node**

There will be a statefulset with a single replica for the boot node.

From the aztec node perspective, it will be started as `start --node --archiver`.

As part of its init container it will deploy the enshrined L1/L2 contracts. Other nodes in the network will be able to resolve the boot node's address via its stable DNS name, e.g. `boot-node-0.aztec-network.svc.cluster.local`.

**full node**

There will be a statefulset for the full nodes, i.e. `start --node --archiver`

The number of replicas will be configurable. Each full node will have a service exposing its p2p port and node port.

As part of their init container, they will get config from the boot node, including its ENR (which will require exposing this on the `get-node-info` endpoint). 

It will be possible to address full nodes individually via their stable DNS name, e.g. `full-node-0.aztec-network.svc.cluster.local`, as well as collectively via a service, e.g. `full-node.aztec-network.svc.cluster.local`.

**validator**

Similar configuration as full nodes, but with a different service name, and started via `start --node --archiver --sequencer`.

The number of replicas will be configurable.

Tests will add/remove validators to/from the L1 validator set.

**prover node**

Same configuration as full nodes, but with a different service name, and started via `start --node --archiver --prover-node`.

The number of replicas will be configurable.

**prover agent**

There will be a deployment for prover agents, and started as `start --prover`.

The number of replicas will be configurable.

**pxe**

PXEs will be deployed as a statefulset.

It will be started as `start --pxe`.

The number of replicas will be configurable. Each PXE will have a service exposing its port.

PXEs will use the collective full node service as their node url by default.

PXEs will only be able to be addressed individually.

**opentel**

There will be a deployment for opentel. It will have a single replica. Nodes in the network will push their logs to opentel.

**prometheus**

There will be a deployment for prometheus. It will have a single replica.

**grafana**

There will be a deployment for graphana. It will have a single replica, and be exposed via ClusterIP.


### Staging Network

We will create a long-lived k8s cluster deployed on AWS. This cluster will be used for running the `staging` network.

We will use this network for long-running stress tests.

There will be a github action workflow that deploys the network to this cluster on every push to the `staging` branch.

The grafana dashboard will be exposed via a public IP, but password protected.

### Production Network

There will be a separate long-lived k8s cluster deployed on AWS. This cluster will be used for running the public `spartan` network.

There will be a github action workflow that deploys the network to this cluster on every push to the `spartan` branch.

When `spartan` is deployed, it will deploy the boot node (pointed at Sepolia) and expose a service bound to a static IP for accessing it. There won't be any full nodes or PXEs deployed by default. The grafana dashboard will be exposed via a public IP, but password protected.

### Chaos

We will add a `chaos` chart within `helm-charts`.

This will have templates in it for enabling chaos, e.g.:

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-failure-example
  namespace: testing-network-namespace
spec:
  action: pod-failure
  mode: one
  duration: '30s'
  selector:
    labelSelectors:
      'app.kubernetes.io/component': 'boot-node'
```

In reality those selectors and durations will be configurable via the `values.yaml` file.

### +network tests

The network tests will use an analogous helper to the `E2E_TEST` in `yarn-projects/end-to-end/Earthfile`.

```dockerfile
NETWORK_TEST:
  FUNCTION
  ARG hardware_concurrency=""
  ARG namespace
  ARG test
  ARG network_values
  ARG chaos_values
  LOCALLY
  # Let docker compose know about the pushed tags above
  ENV AZTEC_DOCKER_TAG=$(git rev-parse HEAD)
  # load the docker image into kind
  RUN kind load docker-image aztecprotocol/end-to-end:$AZTEC_DOCKER_TAG
  RUN helm install aztec-network helm-charts/aztec-network --set $network_values --namespace $namespace
  RUN helm install aztec-chaos helm-charts/aztec-chaos --set $chaos_values --namespace $namespace
  RUN helm test aztec-network --namespace $namespace
```


## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [x] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [x] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [x] DevOps

## Test Plan

### Token Transfer Matrix

We will build out a matrix of conditions to test token transfers. This will include:

- different network topologies (number of nodes, validators, pxes)
- different network conditions (latency, node failures)

Specifically, we will ensure that:

- A block is proposed and added to the Pending Chain
- A block is proven and added to the Proven Chain
- A block is finalized
- The network can tolerate a sequencer going offline
- The network can tolerate a prover going offline
- The network can tolerate a sequencer submitting an invalid block
- The network can tolerate sequencers/validators with slow connections

### Attack Scenarios

We will verify:
- A block proposed without a signature from the current proposer should fail
- A prover submitting a proof with an invalid proof
- A coalition of dishonest sequencers submitting a block with an invalid state transition
- We can tolerate "soft" L1 censorship (i.e. the anvil instance is down for a period of time)

### Existing e2e tests

Existing e2e tests will continue to work as they do now. 

We will gradually port the tests to work with either the existing setup or the new setup, configurable via an environment variable; this likely can be done by simply pointing the wallets that run in the tests to PXEs in the k8s cluster.

## Documentation Plan

We will write documentation on how people can join the `spartan` network. 

## Timeline

- [ ] 2024-08-16: Target Approval Date
- [ ] 2024-08-21: Small network passing token transfer in CI. No chaos.
- [ ] 2024-08-28: Large network passing token transfer in CI with chaos.
- [ ] 2024-09-04: Attack scenarios passing in CI.
- [ ] 2024-09-09: `staging` network deployed
- [ ] 2024-09-11: `spartan` network deployed

## Future Work

There is also [attack net](https://github.com/crytic/attacknet) that works with k8s and chaos-mesh and is purpose built for testing blockchains in adversarial conditions.

This will be useful to add to the network tests, especially around L1 censorship resistance.

