"""Sport seeding lives in the `seed_sports` management command now.

Kept as a thin shim so any straggler imports still work. Running `get_sports`
is a no-op; run `python manage.py seed_sports` instead.
"""

import logging

logger = logging.getLogger(__name__)


class SportCron:
    def get_sports(self):
        logger.warning(
            "SportCron.get_sports is deprecated. Run `python manage.py seed_sports`."
        )
        return False


def get_sports():
    SportCron().get_sports()
