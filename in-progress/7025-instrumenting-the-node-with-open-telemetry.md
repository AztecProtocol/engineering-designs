|                      |                                                                             |
| -------------------- | --------------------------------------------------------------------------- |
| Issue                | [Node metrics](https://github.com/AztecProtocol/aztec-packages/issues/7025) |
| Owners               | @alexghr                                                                    |
| Approvers            |                                                                             |
| Target Approval Date | 2024-06-14                                                                  |

## Executive Summary

The node should emit useful stats about the way its running so that node operators can monitor its performance and resource usage.

## Introduction

In order to confidently deploy and maintain a node in production it needs to provide basic information about how it's operating. These metrics need to be emitted in portable manner so that monitoring tools can easily ingest them. These metrics should be optional such that running a node does not require running any other infrastructure to ingest the metrics.

OpenTelemetry is a framework for capturing instrumentation data from applications and encoding them into a standard format that's vendor neutral. In the past we've used Prometheus and Grafana to capture metrics from services, OpenTelemetry would enable us to continue running that stack while also giving the community the chance to ingest data into different systems (e.g. Clickhouse, DataDog).

Initially the node metrics will include system usage and the Aztec stats emitted during benchmarks, but the metrics service should be flexible enough to accept new stats as they are developed.

## Interface

Enabling metrics in the node would require running an OpenTelemetry Collector to batch the data, a Prometheus instance to ingest all of this data and a Grafana dashboard to render the data. As part of this work the Docker Compose file used to run the Sandbox will be updated to optionally start these three services up.

## Implementation

OpenTelemetry supports three types of instrumentations: metrics, traces and logs. The immediate goal is to get metrics from the node. Traces and logs will be left for a future iteration.

The OpenTelemetry framework is made up of two components: the API and the SDK. Library code is meant to import and use the API to emit traces, metrics and logs while applications are meant to initialize the SDK. The SDK acts as a "backend" for the API, without it every trace, metric and log become no-ops. This would allow to conditionally initialize the SDK depending on whether stats have been enabled by the user.

> [!NOTE]
> The `@opentelemetry/api` and `@opentelemetry/sdk-node` packages use global scope for the backend. This means we can't have two services initialize two SDKs in the same NodeJS process as they'd clash with each other (e.g. running both the node and the pxe in the same process and both initialize an SDK instance.)

### Update

The OpenTelemetry package was wrapped in a custom `@aztec/telemetry` sub-package in the workspace in order to provide custom attributes, metric names and utility functions. See [PR](https://github.com/AztecProtocol/aztec-packages/pull/7102)

### Naming

The OpenTelemetry specification already includes guidelines on telemetry naming. We'll follow the established guidelines:

- we will prefix all metrics with `aztec`
- we will use full stops `.` to separate components of a name (e.g. `aztec.circuit.simulation`)
- we will use base units for values (e.g. `bytes` over `kilobytes` and `seconds` over `milliseconds`)
- we will _not_ include the unit in the name (there's a separate attribute for that, see code examples)
- custom attributes should only be created if an existing semantic attributes does not exist already
- attribute and metric names exist within the same hierarchy and must be unique
- meter names must the class that's being instrumented. In some cases it is acceptable to name a meter with the package name (if the package is instrumented as a whole)

[Metrics guidelines & naming conventions](https://opentelemetry.io/docs/specs/semconv/general/metrics/)

> [!NOTE]
> Prometheus does not accept full-stops `.` in metric names and will replace them with underscores `_` currently. This will change once it fully supports the OpenTelemetry specification. See [prometheus/prometheus#13095](https://github.com/prometheus/prometheus/issues/13095)

### Benchmark metrics

> [!NOTE]
> The implementation has deviated from this code sample, see [below](#implementation-deviations)

All call sites that emit benchmark stats would be extended to also emit an identical metric via OTel:

```ts
// yarn-project/simulator/src/public/public_kernel.ts
import { metrics } from '@opentelemetry/api';
export class RealPublicKernelCircuitSimulator implements PublicKernelCircuitSimulator {
  // ...
  private meter = metrics.getMeter('RealPublicKernelCircuitSimulator');
  private circuitSimulationMetric = this.meter.createHistogram('aztec.circuit.simulation.duration', {
    unit: 's',
  });

  public async publicKernelCircuitSetup(input: PublicKernelCircuitPrivateInputs): Promise<PublicKernelCircuitPublicInputs> {
    // ...

    this.circuitSimulationMetric.record(duration / 1000, {
      "aztec.circuit.name": 'public-kernel-setup',
      "aztec.circuit.input.size": input.toBuffer().length,
      "aztec.circuit.output.size": result.toBuffer().length,
    });

    this.log.debug(`Simulated public kernel setup circuit`, {
      // ...
    } satisfies CircuitSimulationStats);
  }
}
```

> [!NOTE]
> Grafana dashboards will use attribute names to plot individual circuits as needed.
> The input and output size attributes are better attached to a span instead of a histogram record.

[Metrics API](https://opentelemetry.io/docs/specs/otel/metrics/api/)

### SDK initialization

> [!NOTE]
> The implementation has deviated from this code sample, see [below](#implementation-deviations)

```ts
// yarn-project/aztec-node/src/aztec-node/server.ts
export class AztecNodeService implements AztecNode { 
  private sdk: NodeSDK;

  public static async createAndSync(config: AztecNodeConfig) {
    const sdk = new NodeSDK({
      traceExporter: new ConsoleSpanExporter(),
      metricReader: new PeriodicExportingMetricReader({
        exporter: new ConsoleMetricExporter(),
      }),
      instrumentations: [getNodeAutoInstrumentations()],
    });

    sdk.start();
    // ...
  }

  public stop() {
    await this.sdk.stop();
    // ...
  }
}
```

The `getNodeAutoInstrumentations` function from [@opentelemetry/auto-instrumentations-node](https://www.npmjs.com/package/@opentelemetry/auto-instrumentations-node) sets up instrumentation for a [large number of external packages](https://github.com/open-telemetry/opentelemetry-js-contrib/tree/main/metapackages/auto-instrumentations-node#supported-instrumentations), the vast majority of which are not being used by Aztec. It will be replaced with smaller set of instrumentations that's relevant to Aztec

> [!NOTE]
> Starting the SDK will set up the global instances accessible through the `@opentelemetry/api` package so that even external packages can use the backend to expose metrics.

### System metrics

The SDK will be initialized with the [`@opentelemetry/host-metrics`](https://www.npmjs.com/package/@opentelemetry/host-metrics) package to track system resources.

### Exporting data

The main difference between OpenTelemetry and using Prometheus directly is that OpenTelemetry uses a push model (where services push metrics directly to a service/collector), whereas Prometheus uses a pull model (where the prometheus instance scrapes each service individually). Integrating OpenTelemetry would require us to run one extra service in the stack, the OpenTelemetry Collector, that will collect and batch metrics from nodes.

The Sandbox docker compose file will be updated to include an optional OTel connector, Prometheus instance and Grafana dashboard. They will be turned on using compose profiles

```sh
docker compose up --profile metrics
```

The Terraform IaC will also be updated to deploy an OTel collector, a Prometheus instance and a Grafana dashboard.

The Grafana dashboard will contain the benchmark stats and system resource utilization for a node. The dashboard will be stored in the repo as code so it's easy to maintain and extend (instead of manually modifying the dashboard in the GUI).

### Existing benchmark tests

The existing benchmark tests will remain unmodified for now. Ideally we'd find a way to capture the metrics data during test runs and recreate the Markdown comment without the need for logging benchmark metrics to stdout. Given the pluggable architecture of OpenTelemetry we should be able to initialize the SDK with a custom `MetricsExporter` that sends the data directly to the existing ndjson files. This would enable us to remove the dependency on `winston`.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] L1 Contracts
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] Aztec.nr
- [ ] Noir
- [ ] AVM
- [x] Sequencer
- [ ] Fees
- [ ] P2P Network
- [ ] Cryptography
- [x] DevOps

## Test Plan

1. All existing tests should continue to work as before when telemetry is off
2. Optionally write tests that validate that metrics are captured correctly using [custom test exporters](https://opentelemetry.io/docs/concepts/instrumentation/libraries/#testing).

## Documentation Plan

This document will be updated with any deviations from the spec and naming conventions established during implementation.

## Rejection Reason

N/A

## Abandonment Reason

N/A

## Implementation Deviations

### Wrapped package

The `@aztec/telemetry` package wraps the OpenTelemetry API providing type safe metric and attribute names and helper functions:

```ts
// yarn-project/simulator/src/public/public_kernel.ts
import { type TelemetryClient, type Histogram, Metrics, Attributes } from '@aztec/telemetry';

export class RealPublicKernelCircuitSimulator implements PublicKernelCircuitSimulator {

  private circuitSimulationMetric: Histogram;

  constructor(private simulator: SimulationProvider, telemetry: TelemetryClient) {
    this.circuitSimulationMetric = telemetry.getMeter('RealPublicKernelCircuitSimulator').createHistogram(Metrics.CIRCUIT_SIMULATION_DURATION, {
      unit: 's',
    });
  }

  public async publicKernelCircuitSetup(input: PublicKernelCircuitPrivateInputs): Promise<PublicKernelCircuitPublicInputs> {
    // ...

    this.circuitSimulationMetric.record(durationMS / 1000, {
      [Attributes.CIRCUIT_PROTOCOL_NAME]: 'public-kernel-setup',
    });

    this.log.debug(`Simulated public kernel setup circuit`, {
      // ...
    } satisfies CircuitSimulationStats);
  }
}
```

### Separate "instrumentation" class

In some circumstances it makes sense to extract the instrumentation code to a separate class (e.g. when there are multiple possible implementations for an interface):

```ts
export class ProverInstrumentation {
  private simulationDuration: Histogram;
  private witGenDuration: Gauge;
  private provingDuration: Gauge;
  // etc

  constructor(telemetry: TelemetryClient, name: string = 'bb-prover') {
    const meter = telemetry.getMeter(name);
    // create instruments using meter
  }

  // type-safe histogram update
  public recordDuration(
    metric: 'simulationDuration' | 'witGenDuration' | 'provingDuration',
    circuitName: CircuitName,
    timerOrS: Timer | number,
  ) {
    const s = typeof timerOrS === 'number' ? timerOrS : timerOrS.s();
    this[metric].record(s, {
      [Attributes.PROTOCOL_CIRCUIT_NAME]: circuitName,
      [Attributes.PROTOCOL_CIRCUIT_TYPE]: 'server',
    });
  }
}

export class BBNativeRollupProver implements ServerCircuitProver {
  private instrumentation: ProverInstrumentation;
  constructor(private config: BBProverConfig, telemetry: TelemetryClient) {
    this.instrumentation = new ProverInstrumentation(telemetry, "BBNativeRollupProver");
  }

    private async createRecursiveProof() {
      // ...
      this.instrumentation.recordDuration('provingDuration', circuitName, provingResult.durationMs / 1000);
    }
}

export class TestCircuitProver implements ServerCircuitProver {
  private instrumentation: ProverInstrumentation;

  constructor(telemetry: TelemetryClient) {
    this.instrumentation = new ProverInstrumentation(telemetry, "TestCircuitProver");
  }
  
  /**
   * Simulates the base rollup circuit from its inputs.
   * @param input - Inputs to the circuit.
   * @returns The public inputs as outputs of the simulation.
   */
  public async getBaseRollupProof(input: BaseRollupInputs): Promise<PublicInputsAndRecursiveProof<BaseOrMergeRollupPublicInputs>> {
    // ...
    this.instrumentation.recordDuration('simulationDuration', 'base-rollup', timer);
  }
}
```
