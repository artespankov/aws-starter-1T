import csv
from OneTicketLogging import elasticsearch_logger

_logger = elasticsearch_logger(__name__)


class InventoryCalculator:

    def __init__(self, inventory_url):
        self._inventory_url = inventory_url

    def calculate(self) -> int:
        from icalculator.utils import S3InventoryStorage
        total = 0
        storage = S3InventoryStorage(self._inventory_url)
        content = storage.get_content()
        reader = csv.DictReader(content, delimiter="\t")
        for row in reader:
            try:
                cost = float(row.get("Cost", 0))
                quantity = float(row.get("Quantity", 0))
            except ValueError:
                cost, quantity = 0, 0
            total += cost * quantity
        return total
