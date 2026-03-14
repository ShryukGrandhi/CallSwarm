"""Result aggregation agent - combines and ranks call results."""

import logging

from callswarm.models.data_models import CallResult

logger = logging.getLogger(__name__)


def aggregate_results(results: list[CallResult]) -> tuple[list[CallResult], str]:
    """Aggregate and rank call results.

    Returns:
        (ranked_results, summary_text)
    """
    available = [r for r in results if r.available]
    unavailable = [r for r in results if not r.available]

    # Sort available results: those with specific times first, then by rating
    available.sort(
        key=lambda r: (
            -len(r.times),         # more time slots = better
            -r.business.rating,    # higher rating = better
            not r.walk_in,         # walk-in friendly = better
        )
    )

    # Build summary
    if not available:
        summary = f"No availability found. Called {len(results)} businesses."
        if unavailable:
            names = ", ".join(r.business.name for r in unavailable[:5])
            summary += f" Tried: {names}."
    else:
        lines = [f"{len(available)} option(s) available:\n"]
        for r in available:
            time_str = ", ".join(r.times) if r.times else "walk-in" if r.walk_in else "available"
            line = f"  {r.business.name} — {time_str}"
            if r.notes:
                line += f" ({r.notes})"
            lines.append(line)
        summary = "\n".join(lines)

    logger.info("Aggregation: %d available, %d unavailable", len(available), len(unavailable))
    return available + unavailable, summary
