/**
 * This file was auto-generated by Fern from our API Definition.
 */

import * as serializers from "../../../index";
import * as OpikApi from "../../../../api/index";
import * as core from "../../../../core";

export const SpanSearchStreamRequestPublicType: core.serialization.Schema<
    serializers.SpanSearchStreamRequestPublicType.Raw,
    OpikApi.SpanSearchStreamRequestPublicType
> = core.serialization.enum_(["general", "tool", "llm", "guardrail"]);

export declare namespace SpanSearchStreamRequestPublicType {
    export type Raw = "general" | "tool" | "llm" | "guardrail";
}
