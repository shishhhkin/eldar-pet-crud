import os

import pytest

EXTERNAL_LIBRARY_URL = os.environ.get('EXTERNAL_LIBRARY_URL')

requires_library = pytest.mark.skipif(
    EXTERNAL_LIBRARY_URL is None, reason='EXTERNAL_LIBRARY_URL is not set'
)
