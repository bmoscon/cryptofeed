from cryptofeed.rest.api import API
from cryptofeed.feeds import GEMINI
from cryptofeed.log import get_logger

LOG = get_logger('rest', 'rest.log')

class Gemini(API):
    ID = GEMINI
