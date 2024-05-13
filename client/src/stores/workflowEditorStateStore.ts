import type { UseElementBoundingReturn } from "@vueuse/core";
import { defineStore } from "pinia";
import type { UnwrapRef } from "vue";
import Vue, { reactive } from "vue";

import type { OutputTerminals } from "@/components/Workflow/Editor/modules/terminals";

import { useScopePointerStore } from "./scopePointerStore";

export interface InputTerminalPosition {
    endX: number;
    endY: number;
}

export interface OutputTerminalPosition {
    startX: number;
    startY: number;
}

export type TerminalPosition = InputTerminalPosition & OutputTerminalPosition;

export interface XYPosition {
    x: number;
    y: number;
}

interface State {
    inputTerminals: { [index: number]: { [index: string]: InputTerminalPosition } };
    outputTerminals: { [index: number]: { [index: string]: OutputTerminalPosition } };
    draggingPosition: TerminalPosition | null;
    draggingTerminal: OutputTerminals | null;
    activeNodeId: number | null;
    scale: number;
    stepPosition: { [index: number]: UnwrapRef<UseElementBoundingReturn> };
    stepLoadingState: { [index: number]: { loading?: boolean; error?: string } };
}

export const useWorkflowStateStore = (workflowId: string) => {
    const { scope } = useScopePointerStore();

    return defineStore(`workflowStateStore${scope(workflowId)}`, {
        state: (): State => ({
            inputTerminals: {},
            outputTerminals: {},
            draggingPosition: null,
            draggingTerminal: null,
            activeNodeId: null,
            scale: 1,
            stepPosition: {},
            stepLoadingState: {},
        }),
        getters: {
            getInputTerminalPosition(state: State) {
                return (stepId: number, inputName: string) => {
                    return state.inputTerminals[stepId]?.[inputName] as InputTerminalPosition | undefined;
                };
            },
            getOutputTerminalPosition(state: State) {
                return (stepId: number, outputName: string) => {
                    return state.outputTerminals[stepId]?.[outputName] as OutputTerminalPosition | undefined;
                };
            },
            getStepLoadingState(state: State) {
                return (stepId: number) => state.stepLoadingState[stepId];
            },
        },
        actions: {
            setInputTerminalPosition(stepId: number, inputName: string, position: InputTerminalPosition) {
                if (!this.inputTerminals[stepId]) {
                    Vue.set(this.inputTerminals, stepId, {});
                }

                Vue.set(this.inputTerminals[stepId]!, inputName, position);
            },
            setOutputTerminalPosition(stepId: number, outputName: string, position: OutputTerminalPosition) {
                if (!this.outputTerminals[stepId]) {
                    Vue.set(this.outputTerminals, stepId, reactive({}));
                }

                Vue.set(this.outputTerminals[stepId]!, outputName, position);
            },
            deleteInputTerminalPosition(stepId: number, inputName: string) {
                delete this.inputTerminals[stepId]?.[inputName];
            },
            deleteOutputTerminalPosition(stepId: number, outputName: string) {
                delete this.outputTerminals[stepId]?.[outputName];
            },
            setActiveNode(nodeId: number | null) {
                this.activeNodeId = nodeId;
            },
            setScale(scale: number) {
                this.scale = scale;
            },
            setStepPosition(stepId: number, position: UnwrapRef<UseElementBoundingReturn>) {
                Vue.set(this.stepPosition, stepId, position);
            },
            deleteStepPosition(stepId: number) {
                delete this.stepPosition[stepId];
            },
            setLoadingState(stepId: number, loading: boolean, error: string | undefined) {
                Vue.set(this.stepLoadingState, stepId, { loading, error });
            },
        },
    })();
};
