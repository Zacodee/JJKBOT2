"""Tests du démarrage résilient : détection du refus 429 / Cloudflare 1015.

Sur un hébergeur qui relance le process à chaque crash, sortir immédiatement
après un 429 entretient le blocage. `_is_rate_limited` sert à distinguer ce cas
(réessayer après une pause) des erreurs définitives (mauvais token), qui
doivent remonter tout de suite.
"""

from __future__ import annotations

import unittest
from unittest import mock

import discord

import main


class _FakeResponse:
    def __init__(self, status: int, reason: str = "Too Many Requests") -> None:
        self.status = status
        self.reason = reason


def _http_error(status: int, text: str) -> discord.HTTPException:
    return discord.HTTPException(_FakeResponse(status), text)


class RateLimitDetectionTests(unittest.TestCase):
    def test_429_is_detected(self) -> None:
        error = _http_error(429, "Too Many Requests")
        self.assertTrue(main._is_rate_limited(error))

    def test_cloudflare_1015_html_is_detected(self) -> None:
        html = '<html><title>Access denied | discord.com used Cloudflare</title>Error 1015'
        self.assertTrue(main._is_rate_limited(_http_error(429, html)))

    def test_other_http_error_is_not_retried(self) -> None:
        self.assertFalse(main._is_rate_limited(_http_error(401, "Unauthorized")))
        self.assertFalse(main._is_rate_limited(_http_error(500, "Internal Server Error")))

    def test_unrelated_exception_is_not_retried(self) -> None:
        self.assertFalse(main._is_rate_limited(ValueError("boom")))

    def test_backoff_grows_then_stays_flat(self) -> None:
        delays = main.RATE_LIMIT_BACKOFF
        self.assertGreaterEqual(len(delays), 2)
        self.assertEqual(list(delays), sorted(delays))
        # Le dernier palier est réutilisé : la série ne s'allonge pas à l'infini.
        self.assertEqual(delays[min(99, len(delays) - 1)], delays[-1])


class RetryLoopTests(unittest.TestCase):
    """`_run_with_retry` doit patienter sur un 429 et exploser sur le reste."""

    def _patch_bot(self, errors: list[BaseException]) -> mock.Mock:
        """Faux bot : chaque `run()` lève l’erreur suivante, puis rend la main."""
        calls = {"n": 0}

        def fake_run(self, *args, **kwargs) -> None:
            index = calls["n"]
            calls["n"] += 1
            if index < len(errors):
                raise errors[index]

        return mock.patch.object(main.JJKBot, "run", fake_run)

    def test_429_waits_then_retries_and_succeeds(self) -> None:
        sleeps: list[float] = []
        with self._patch_bot([_http_error(429, "Too Many Requests")]), mock.patch.object(
            main.time, "sleep", sleeps.append
        ), mock.patch.object(main.config, "token", return_value="fake"):
            main._run_with_retry(sync_only=False)  # rend la main au 2e essai
        self.assertEqual(sleeps, [main.RATE_LIMIT_BACKOFF[0]])

    def test_repeated_429_keeps_retrying_with_capped_delay(self) -> None:
        sleeps: list[float] = []
        errors = [_http_error(429, "Too Many Requests")] * (len(main.RATE_LIMIT_BACKOFF) + 2)
        with self._patch_bot(errors), mock.patch.object(
            main.time, "sleep", sleeps.append
        ), mock.patch.object(main.config, "token", return_value="fake"):
            main._run_with_retry(sync_only=False)
        self.assertEqual(len(sleeps), len(errors))
        self.assertEqual(sleeps[-1], main.RATE_LIMIT_BACKOFF[-1])

    def test_non_rate_limit_error_propagates_without_sleep(self) -> None:
        sleeps: list[float] = []
        with self._patch_bot([_http_error(401, "Unauthorized")]), mock.patch.object(
            main.time, "sleep", sleeps.append
        ), mock.patch.object(main.config, "token", return_value="fake"):
            with self.assertRaises(discord.HTTPException):
                main._run_with_retry(sync_only=False)
        self.assertEqual(sleeps, [])


if __name__ == "__main__":
    unittest.main()
