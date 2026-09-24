# All costs are stored as integer microdollars.
# 1 USD = 1,000,000 microdollars.
#
# Pinned pricing model for this capstone:
# Gemini 2.5 Flash, <= 200k-token prompts.
#
# Input:        $0.30 / 1M tokens
# Cached input: $0.03 / 1M tokens
# Output:       $2.50 / 1M tokens
#
# Reasoning/thinking tokens are charged at the output rate.

MICRODOLLARS_PER_DOLLAR = 1_000_000

INPUT_COST_PER_MILLION = 300_000
CACHED_INPUT_COST_PER_MILLION = 30_000
OUTPUT_COST_PER_MILLION = 2_500_000
REASONING_COST_PER_MILLION = OUTPUT_COST_PER_MILLION


def _token_cost(token_count: int, rate_per_million: int) -> int:
    if token_count < 0:
        raise ValueError("Token count cannot be negative")

    return (token_count * rate_per_million) // 1_000_000


def calculate_token_cost(
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> dict:
    input_cost = _token_cost(
        input_tokens,
        INPUT_COST_PER_MILLION,
    )

    cached_input_cost = _token_cost(
        cached_input_tokens,
        CACHED_INPUT_COST_PER_MILLION,
    )

    output_cost = _token_cost(
        output_tokens,
        OUTPUT_COST_PER_MILLION,
    )

    reasoning_cost = _token_cost(
        reasoning_tokens,
        REASONING_COST_PER_MILLION,
    )

    total_cost = (
        input_cost
        + cached_input_cost
        + output_cost
        + reasoning_cost
    )

    return {
        "currency": "USD",
        "unit": "microdollars",
        "input_cost": input_cost,
        "cached_input_cost": cached_input_cost,
        "output_cost": output_cost,
        "reasoning_cost": reasoning_cost,
        "total_cost": total_cost,
    }