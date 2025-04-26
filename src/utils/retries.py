from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type


def retry_on_exception():
    """
    Decorator to retry functions on any exception with exponential backoff.
    Retries up to 3 times with increasing wait intervals (1s to 10s).
    """
    return retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception)
    )
