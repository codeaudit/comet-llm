import math
from functools import cached_property
from typing import Any, Optional, TYPE_CHECKING, Union
import pydantic
import json

if TYPE_CHECKING:
    from litellm.types.utils import ModelResponse

from opik.evaluation.metrics import base_metric, score_result
from opik.evaluation.models import base_model, models_factory
from opik.logging_messages import GEVAL_SCORE_CALC_FAILED
from .template import G_EVAL_COT_TEMPLATE, G_EVAL_QUERY_TEMPLATE
from opik import exceptions
from .. import parsing_helpers


class GEvalScoreFormat(pydantic.BaseModel):
    score: int
    reason: str


class GEval(base_metric.BaseMetric):
    def __init__(
        self,
        task_introduction: str,
        evaluation_criteria: str,
        model: Optional[Union[str, base_model.OpikBaseModel]] = None,
        name: str = "g_eval_metric",
        track: bool = True,
    ):
        """
        A metric that evaluates an LLM output based on chain-of-thought built with the evaluation criteria provided
        by the user.

        For more details see the original paper: https://arxiv.org/pdf/2303.16634

        Args:
            task_introduction: An instruction for LLM used to generate an evaluation chain-of-thought and in evaluation call itself.
                `opik.evaluation.models.LiteLLMChatModel` is used by default.
            evaluation_criteria: The main task for G-Eval metric written in human language.
            model: The LLM to use for evaluation. Can be a string (model name) or an `opik.evaluation.models.OpikBaseModel` subclass instance.
            name: The name of the metric.
            track: Whether to track the metric. Defaults to True.
        """
        super().__init__(
            name=name,
            track=track,
        )
        self._init_model(model)

        self.task_introduction = task_introduction
        self.evaluation_criteria = evaluation_criteria
        self._log_probs_supported = False

    @cached_property
    def llm_chain_of_thought(self) -> str:
        prompt = G_EVAL_COT_TEMPLATE.format(
            task_introduction=self.task_introduction,
            evaluation_criteria=self.evaluation_criteria,
        )
        return self._model.generate_string(input=prompt)

    def _init_model(
        self, model: Optional[Union[str, base_model.OpikBaseModel]]
    ) -> None:
        if isinstance(model, base_model.OpikBaseModel):
            self._model = model
        else:
            self._model = models_factory.get(model_name=model)

            if (
                hasattr(self._model, "supported_params")
                and "logprobs" in self._model.supported_params
                and "top_logprobs" in self._model.supported_params
            ):
                self._log_probs_supported = True

    def score(
        self,
        output: str,
        **ignored_kwargs: Any,
    ) -> score_result.ScoreResult:
        """
        Calculate the G-Eval score for the given LLM's output.

        Args:
            output: The LLM's output to evaluate.
            **ignored_kwargs: Additional keyword arguments that are ignored.

        Returns:
            score_result.ScoreResult: A ScoreResult object containing the G-Eval score
            (between 0.0 and 1.0) and a reason for the score.
        """
        llm_query = G_EVAL_QUERY_TEMPLATE.format(
            task_introduction=self.task_introduction,
            evaluation_criteria=self.evaluation_criteria,
            chain_of_thought=self.llm_chain_of_thought,
            input=output,
        )

        request = [
            {
                "content": llm_query,
                "role": "user",
            },
        ]

        model_output = self._model.generate_provider_response(
            messages=request,
            logprobs=self._log_probs_supported,
            top_logprobs=20 if self._log_probs_supported else None,
            response_format=GEvalScoreFormat,
        )

        return self._parse_model_output(model_output)

    async def ascore(
        self, output: str, **ignored_kwargs: Any
    ) -> score_result.ScoreResult:
        """
        Calculate the G-Eval score for the given LLM's output.

        Args:
            output: The LLM's output to evaluate.
            **ignored_kwargs: Additional keyword arguments that are ignored.

        Returns:
            score_result.ScoreResult: A ScoreResult object containing the G-Eval score
            (between 0.0 and 1.0) and a reason for the score.
        """
        llm_query = G_EVAL_QUERY_TEMPLATE.format(
            task_introduction=self.task_introduction,
            evaluation_criteria=self.evaluation_criteria,
            chain_of_thought=self.llm_chain_of_thought,
            input=output,
        )

        request = [
            {
                "content": llm_query,
                "role": "user",
            },
        ]

        model_output = await self._model.agenerate_provider_response(
            messages=request,
            logprobs=self._log_probs_supported,
            top_logprobs=20 if self._log_probs_supported else None,
            response_format=GEvalScoreFormat,
        )

        return self._parse_model_output(model_output)

    def _parse_model_output(self, content: "ModelResponse") -> score_result.ScoreResult:
        """
        This method computes the final score based on the model's response. The model's response is a dictionary
        with a `score` key and a `reason` key. The prompt template also specifies that the score should be an integer
        between 0 and 10.

        In order to make the score computation more robust, we look at the top logprobs of the score token and compute
        a weighted average of the scores. Since we try to enforce the format of the model's response, we can assume that
        the score token is always the fourth token in the response (first token is `{"`, followed by `score` and `":`).
        """
        try:
            if not self._log_probs_supported:
                dict_content = parsing_helpers.extract_json_content_or_raise(
                    content.choices[0].message.content
                )

                score = float(dict_content["score"])
                if not 0 <= score <= 10:
                    raise ValueError

                reason = str(dict_content["reason"])

                return score_result.ScoreResult(
                    name=self.name,
                    value=score / 10,
                    reason=reason,
                )

            else:
                # Compute score using top logprobs
                score_token_position = 3
                log_probs_content = content.choices[0].model_extra["logprobs"][
                    "content"
                ][score_token_position]

                top_score_logprobs = log_probs_content["top_logprobs"]
                log_probs_token = log_probs_content["token"]

                linear_probs_sum = 0.0
                weighted_score_sum = 0.0

                for token_info in top_score_logprobs:
                    # litellm in v1.60.2 (or earlier) started provide logprobes
                    # as pydantic model, not just dict
                    # we will convert model to dict to provide backward compatability
                    if not isinstance(token_info, dict):
                        token_info = token_info.model_dump()

                    # if not a number
                    if not token_info["token"].isdecimal():
                        continue

                    score = int(token_info["token"])

                    # if score value not in scale
                    if not 0 <= score <= 10:
                        continue

                    log_prob = token_info["logprob"]
                    linear_prob = math.exp(log_prob)

                    linear_probs_sum += linear_prob
                    weighted_score_sum += linear_prob * score

                if linear_probs_sum != 0.0:
                    final_score: float = weighted_score_sum / linear_probs_sum / 10
                else:
                    # Handle cases where we can't find any matching tokens in the top_log_probs
                    if not log_probs_token.isdecimal():
                        raise exceptions.MetricComputationError(GEVAL_SCORE_CALC_FAILED)

                    final_score = int(log_probs_token) / 10

                if not (0.0 <= final_score <= 1.0):
                    raise ValueError

                # Get the reason
                reason = json.loads(content.choices[0].message.content)["reason"]

                # Return the score and the reason
                return score_result.ScoreResult(
                    name=self.name, value=final_score, reason=reason
                )
        except Exception:
            raise exceptions.MetricComputationError(GEVAL_SCORE_CALC_FAILED)
