from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from src.challenge import challenge_present


class ChallengeDetectionTest(IsolatedAsyncioTestCase):
    async def test_precursor_script_alone_is_not_a_challenge(self):
        page = self.page_with_scripts("/cdn-cgi/challenge-platform/scripts/precursor/main.js")

        self.assertFalse(await challenge_present(page))

    async def test_orchestrated_challenge_is_detected(self):
        page = self.page_with_scripts(
            "/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1"
        )

        self.assertTrue(await challenge_present(page))

    async def test_challenge_form_is_detected(self):
        page = self.page_with_scripts(challenge_form=True)

        self.assertTrue(await challenge_present(page))

    @staticmethod
    def page_with_scripts(*scripts: str, challenge_form: bool = False) -> MagicMock:
        page = MagicMock()

        def locator(selector: str) -> MagicMock:
            match selector:
                case 'script[src*="/cdn-cgi/challenge-platform/"][src*="/orchestrate/"]':
                    present = any(
                        "/cdn-cgi/challenge-platform/" in src and "/orchestrate/" in src
                        for src in scripts
                    )
                case "#challenge-form":
                    present = challenge_form
                case _:
                    raise AssertionError(f"Unexpected selector: {selector}")
            return MagicMock(count=AsyncMock(return_value=int(present)))

        page.locator.side_effect = locator
        return page
