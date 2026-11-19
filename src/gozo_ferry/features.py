import logging

logger = logging.getLogger(__name__)


def knots_to_kmh(df, factor):
    """Convert the 'wind' column from knots to km/h. Never modifies its input."""
    out = df.copy()
    out["wind"] = out["wind"] * factor
    logger.info("Wind converted to km/h using factor=%.3f", factor)
    return out
