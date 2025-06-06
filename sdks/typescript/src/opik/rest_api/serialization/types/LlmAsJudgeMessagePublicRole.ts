/**
 * This file was auto-generated by Fern from our API Definition.
 */

import * as serializers from "../index";
import * as OpikApi from "../../api/index";
import * as core from "../../core";

export const LlmAsJudgeMessagePublicRole: core.serialization.Schema<
    serializers.LlmAsJudgeMessagePublicRole.Raw,
    OpikApi.LlmAsJudgeMessagePublicRole
> = core.serialization.enum_(["SYSTEM", "USER", "AI", "TOOL_EXECUTION_RESULT"]);

export declare namespace LlmAsJudgeMessagePublicRole {
    export type Raw = "SYSTEM" | "USER" | "AI" | "TOOL_EXECUTION_RESULT";
}
