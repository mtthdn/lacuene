#!/usr/bin/env python3
"""
Shared HTTP utilities for normalizer scripts.

Provides fetch_with_retry and fetch_json_with_retry with exponential backoff,
rate-limit awareness (Retry-After), and retries on transient server errors.
"""

import sys
import time

import requests


def fetch_with_retry(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> requests.Response:
    """
    HTTP GET with exponential backoff on transient failures.

    Retries on:
      - HTTP 429 (rate limit) -- respects Retry-After header if present
      - HTTP 5xx (server errors)
      - Connection/timeout errors

    Raises immediately on:
      - HTTP 4xx (client errors) other than 429

    Returns the requests.Response on success.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)

            if resp.status_code == 429:
                if attempt >= max_retries:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        wait = float(retry_after)
                    except (ValueError, TypeError):
                        wait = backoff_base ** attempt
                else:
                    wait = backoff_base ** attempt
                print(
                    f"  RETRY {attempt + 1}/{max_retries}: 429 rate-limited, "
                    f"waiting {wait:.1f}s -- {url}",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            if 500 <= resp.status_code < 600:
                if attempt >= max_retries:
                    resp.raise_for_status()
                wait = backoff_base ** attempt
                print(
                    f"  RETRY {attempt + 1}/{max_retries}: HTTP {resp.status_code}, "
                    f"waiting {wait:.1f}s -- {url}",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            # Non-retryable 4xx errors: raise immediately
            resp.raise_for_status()
            return resp

        except requests.exceptions.ConnectionError as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            wait = backoff_base ** attempt
            print(
                f"  RETRY {attempt + 1}/{max_retries}: connection error, "
                f"waiting {wait:.1f}s -- {url}",
                file=sys.stderr,
            )
            time.sleep(wait)

        except requests.exceptions.Timeout as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            wait = backoff_base ** attempt
            print(
                f"  RETRY {attempt + 1}/{max_retries}: timeout, "
                f"waiting {wait:.1f}s -- {url}",
                file=sys.stderr,
            )
            time.sleep(wait)

    # Should not reach here, but just in case
    if last_exc:
        raise last_exc
    raise RuntimeError(f"fetch_with_retry exhausted retries for {url}")


def fetch_json_with_retry(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> dict | list:
    """
    HTTP GET with retry, returning parsed JSON.

    Calls fetch_with_retry and returns response.json().
    """
    resp = fetch_with_retry(
        url,
        params=params,
        headers=headers,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )
    return resp.json()


def post_with_retry(
    url: str,
    json_body: dict | None = None,
    headers: dict | None = None,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> requests.Response:
    """
    HTTP POST with exponential backoff on transient failures.

    Same retry semantics as fetch_with_retry but for POST requests
    with a JSON body.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                url, json=json_body, headers=headers, timeout=30
            )

            if resp.status_code == 429:
                if attempt >= max_retries:
                    resp.raise_for_status()
                retry_after = resp.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        wait = float(retry_after)
                    except (ValueError, TypeError):
                        wait = backoff_base ** attempt
                else:
                    wait = backoff_base ** attempt
                print(
                    f"  RETRY {attempt + 1}/{max_retries}: 429 rate-limited, "
                    f"waiting {wait:.1f}s -- {url}",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            if 500 <= resp.status_code < 600:
                if attempt >= max_retries:
                    resp.raise_for_status()
                wait = backoff_base ** attempt
                print(
                    f"  RETRY {attempt + 1}/{max_retries}: HTTP {resp.status_code}, "
                    f"waiting {wait:.1f}s -- {url}",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        except requests.exceptions.ConnectionError as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            wait = backoff_base ** attempt
            print(
                f"  RETRY {attempt + 1}/{max_retries}: connection error, "
                f"waiting {wait:.1f}s -- {url}",
                file=sys.stderr,
            )
            time.sleep(wait)

        except requests.exceptions.Timeout as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            wait = backoff_base ** attempt
            print(
                f"  RETRY {attempt + 1}/{max_retries}: timeout, "
                f"waiting {wait:.1f}s -- {url}",
                file=sys.stderr,
            )
            time.sleep(wait)

    if last_exc:
        raise last_exc
    raise RuntimeError(f"post_with_retry exhausted retries for {url}")


def post_json_with_retry(
    url: str,
    json_body: dict | None = None,
    headers: dict | None = None,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> dict | list:
    """
    HTTP POST with retry, returning parsed JSON.

    Calls post_with_retry and returns response.json().
    """
    resp = post_with_retry(
        url,
        json_body=json_body,
        headers=headers,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )
    return resp.json()
