import { defineStore } from "pinia";
import Vue from "vue";

import type { CollectionTypeDescriptor } from "@/components/Workflow/Editor/modules/collectionTypeDescription";
import { type Connection, getConnectionId, useConnectionStore } from "@/stores/workflowConnectionStore";
import { assertDefined } from "@/utils/assertions";

import { useScopePointerStore } from "./scopePointerStore";

interface State {
    steps: { [index: string]: Step };
    stepIndex: number;
    stepMapOver: { [index: number]: CollectionTypeDescriptor };
    stepInputMapOver: StepInputMapOver;
    stepExtraInputs: { [index: number]: InputTerminalSource[] };
}

interface StepPosition {
    top: number;
    left: number;
}

/*
      "ChangeDatatypeActionout_file1": {
        "action_type": "ChangeDatatypeAction",
        "output_name": "out_file1",
        "action_arguments": {
          "newtype": "ab1"
        }
      }
*/

export interface PostJobAction {
    action_type: string;
    output_name: string;
    action_arguments: {
        [index: string]: string;
    };
}

export interface PostJobActions {
    [index: string]: PostJobAction;
}

export interface DataOutput {
    extensions: string[];
    name: string;
    optional: boolean;
}

export interface CollectionOutput extends Omit<DataOutput, "type"> {
    collection: boolean;
    collection_type: string;
    collection_type_source: string | null;
}

export declare const ParameterTypes: "text" | "integer" | "float" | "boolean" | "color";
export interface ParameterOutput extends Omit<DataOutput, "type" | "extensions"> {
    type: typeof ParameterTypes;
    parameter: true;
}

interface BaseStepInput {
    valid?: boolean;
    name: string;
    label: string;
    multiple: boolean;
    extensions: string[];
    optional: boolean;
    input_type: string;
    input_subworkflow_step_id?: number;
}

export interface DataStepInput extends BaseStepInput {
    input_type: "dataset";
}

export interface DataCollectionStepInput extends BaseStepInput {
    input_type: "dataset_collection";
    collection_types: string[];
}

export interface ParameterStepInput extends Omit<BaseStepInput, "input_type"> {
    input_type: "parameter";
    type: typeof ParameterTypes;
}

export type InputTerminalSource = DataStepInput | DataCollectionStepInput | ParameterStepInput;
export type OutputTerminalSource = DataOutput | CollectionOutput | ParameterOutput;
export type TerminalSource = InputTerminalSource | OutputTerminalSource;

interface WorkflowOutput {
    output_name: string;
    label?: string | null;
    uuid?: string | null;
}

export interface NewStep {
    annotation?: string;
    config_form?: { [index: string]: any };
    content_id?: string | null;
    id?: number;
    errors?: string[] | null;
    input_connections: StepInputConnection;
    inputs: Array<InputTerminalSource>;
    label?: string | null;
    name: string;
    outputs: Array<OutputTerminalSource>;
    position?: StepPosition;
    post_job_actions?: PostJobActions;
    tool_state: Record<string, unknown>;
    tool_version?: string;
    tooltip?: string;
    type: "tool" | "data_input" | "data_collection_input" | "subworkflow" | "parameter_input" | "pause";
    uuid?: string;
    when?: string | null;
    workflow_outputs?: WorkflowOutput[];
}

export interface Step extends NewStep {
    id: number;
}

export interface Steps {
    [index: string]: Step;
}

export interface StepInputConnection {
    [index: string]: ConnectionOutputLink | ConnectionOutputLink[] | undefined;
}

export interface ConnectionOutputLink {
    output_name: string;
    id: number;
    input_subworkflow_step_id?: number;
}

export interface WorkflowOutputs {
    [index: string]: {
        stepId: number;
        outputName: string;
    };
}

interface StepInputMapOver {
    [index: number]: { [index: string]: CollectionTypeDescriptor };
}

export const useWorkflowStepStore = (workflowId: string) => {
    const { scope } = useScopePointerStore();

    return defineStore(`workflowStepStore${scope(workflowId)}`, {
        state: (): State => ({
            steps: {} as Steps,
            stepMapOver: {} as { [index: number]: CollectionTypeDescriptor },
            stepInputMapOver: {} as StepInputMapOver,
            stepIndex: -1,
            stepExtraInputs: {} as { [index: number]: InputTerminalSource[] },
        }),
        getters: {
            getStep(state: State) {
                return (stepId: number): Step | undefined => {
                    return state.steps[stepId.toString()];
                };
            },
            getStepExtraInputs(state: State) {
                return (stepId: number) => state.stepExtraInputs[stepId] || [];
            },
            getStepIndex(state: State) {
                return Math.max(...Object.values(state.steps).map((step) => step.id), state.stepIndex);
            },
            hasActiveOutputs(state: State) {
                return Boolean(Object.values(state.steps).find((step) => step.workflow_outputs?.length));
            },
            workflowOutputs(state: State) {
                const workflowOutputs: WorkflowOutputs = {};
                Object.values(state.steps).forEach((step) => {
                    if (step.workflow_outputs?.length) {
                        step.workflow_outputs.forEach((workflowOutput) => {
                            if (workflowOutput.label) {
                                workflowOutputs[workflowOutput.label] = {
                                    outputName: workflowOutput.output_name,
                                    stepId: step.id,
                                };
                            }
                        });
                    }
                });
                return workflowOutputs;
            },
            duplicateLabels(state: State) {
                const duplicateLabels: Set<string> = new Set();
                const labels: Set<string> = new Set();
                Object.values(state.steps).forEach((step) => {
                    if (step.workflow_outputs?.length) {
                        step.workflow_outputs.forEach((workflowOutput) => {
                            if (workflowOutput.label) {
                                if (labels.has(workflowOutput.label)) {
                                    duplicateLabels.add(workflowOutput.label);
                                }
                                labels.add(workflowOutput.label);
                            }
                        });
                    }
                });
                return duplicateLabels;
            },
        },
        actions: {
            addStep(newStep: NewStep): Step {
                const stepId = newStep.id ? newStep.id : this.getStepIndex + 1;
                const step = Object.freeze({ ...newStep, id: stepId } as Step);
                Vue.set(this.steps, stepId.toString(), step);
                const connectionStore = useConnectionStore(workflowId);
                stepToConnections(step).map((connection) => connectionStore.addConnection(connection));
                this.stepExtraInputs[step.id] = getStepExtraInputs(step);
                return step;
            },
            insertNewStep(
                contentId: NewStep["content_id"],
                name: NewStep["name"],
                type: NewStep["type"],
                position: NewStep["position"]
            ) {
                const stepData: NewStep = {
                    name: name,
                    content_id: contentId,
                    input_connections: {},
                    type: type,
                    inputs: [],
                    outputs: [],
                    position: position,
                    post_job_actions: {},
                    tool_state: {},
                };
                return this.addStep(stepData);
            },
            updateStep(this: State, step: Step) {
                const workflow_outputs = step.workflow_outputs?.filter((workflowOutput) =>
                    step.outputs.find((output) => workflowOutput.output_name == output.name)
                );
                this.steps[step.id.toString()] = Object.freeze({ ...step, workflow_outputs });
                this.stepExtraInputs[step.id] = getStepExtraInputs(step);
            },
            changeStepMapOver(stepId: number, mapOver: CollectionTypeDescriptor) {
                Vue.set(this.stepMapOver, stepId, mapOver);
            },
            resetStepInputMapOver(stepId: number) {
                Vue.set(this.stepInputMapOver, stepId, {});
            },
            changeStepInputMapOver(stepId: number, inputName: string, mapOver: CollectionTypeDescriptor) {
                if (this.stepInputMapOver[stepId]) {
                    Vue.set(this.stepInputMapOver[stepId]!, inputName, mapOver);
                } else {
                    Vue.set(this.stepInputMapOver, stepId, { [inputName]: mapOver });
                }
            },
            addConnection(connection: Connection) {
                const inputStep = this.getStep(connection.input.stepId);
                assertDefined(
                    inputStep,
                    `Failed to add connection, because step with id ${connection.input.stepId} is undefined`
                );
                const input = inputStep.inputs.find((input) => input.name === connection.input.name);
                const connectionLink: ConnectionOutputLink = {
                    output_name: connection.output.name,
                    id: connection.output.stepId,
                };
                if (input && "input_subworkflow_step_id" in input && input.input_subworkflow_step_id !== undefined) {
                    connectionLink["input_subworkflow_step_id"] = input.input_subworkflow_step_id;
                }
                let connectionLinks: ConnectionOutputLink[] = [connectionLink];
                let inputConnection = inputStep.input_connections[connection.input.name];
                if (inputConnection) {
                    if (!Array.isArray(inputConnection)) {
                        inputConnection = [inputConnection];
                    }
                    inputConnection = inputConnection.filter(
                        (connection) =>
                            !(
                                connection.id === connectionLink.id &&
                                connection.output_name === connectionLink.output_name
                            )
                    );
                    connectionLinks = [...connectionLinks, ...inputConnection];
                }
                const updatedStep = {
                    ...inputStep,
                    input_connections: {
                        ...inputStep.input_connections,
                        [connection.input.name]: connectionLinks.sort((a, b) =>
                            a.id === b.id ? a.output_name.localeCompare(b.output_name) : a.id - b.id
                        ),
                    },
                };
                this.updateStep(updatedStep);
            },
            removeConnection(connection: Connection) {
                const inputStep = this.getStep(connection.input.stepId);
                assertDefined(
                    inputStep,
                    `Failed to remove connection, because step with id ${connection.input.stepId} is undefined`
                );

                const inputConnections = inputStep.input_connections[connection.input.name];
                if (this.getStepExtraInputs(inputStep.id).find((input) => connection.input.name === input.name)) {
                    inputStep.input_connections[connection.input.name] = undefined;
                } else {
                    if (Array.isArray(inputConnections)) {
                        inputStep.input_connections[connection.input.name] = inputConnections.filter(
                            (outputLink) =>
                                !(outputLink.id === connection.output.stepId,
                                outputLink.output_name === connection.output.name)
                        );
                    } else {
                        Vue.delete(inputStep.input_connections, connection.input.name);
                    }
                }
                this.updateStep(inputStep);
            },
            removeStep(this: State, stepId: number) {
                const connectionStore = useConnectionStore(workflowId);
                connectionStore
                    .getConnectionsForStep(stepId)
                    .forEach((connection) => connectionStore.removeConnection(getConnectionId(connection)));
                Vue.delete(this.steps, stepId.toString());
                Vue.delete(this.stepExtraInputs, stepId);
            },
        },
    })();
};

export function stepToConnections(step: Step): Connection[] {
    const connections: Connection[] = [];
    if (step.input_connections) {
        Object.entries(step?.input_connections).forEach(([inputName, outputArray]) => {
            if (outputArray === undefined) {
                return;
            }
            if (!Array.isArray(outputArray)) {
                outputArray = [outputArray];
            }
            outputArray.forEach((output) => {
                const connection: Connection = {
                    input: {
                        stepId: step.id,
                        name: inputName,
                        connectorType: "input",
                    },
                    output: {
                        stepId: output.id,
                        name: output.output_name,
                        connectorType: "output",
                    },
                };
                const connectionInput = step.inputs.find((input) => input.name == inputName);
                if (connectionInput && "input_subworkflow_step_id" in connectionInput) {
                    connection.input.input_subworkflow_step_id = connectionInput.input_subworkflow_step_id;
                }
                connections.push(connection);
            });
        });
    }
    return connections;
}

function getStepExtraInputs(step: Step) {
    const extraInputs: InputTerminalSource[] = [];
    if (step.when !== undefined) {
        Object.keys(step.input_connections).forEach((inputName) => {
            if (!step.inputs.find((input) => input.name === inputName) && step.when?.includes(inputName)) {
                const terminalSource = {
                    name: inputName,
                    optional: false,
                    input_type: "parameter" as const,
                    type: "boolean" as const,
                    multiple: false,
                    label: inputName,
                    extensions: [],
                };
                extraInputs.push(terminalSource);
            }
        });
    }
    return extraInputs;
}
