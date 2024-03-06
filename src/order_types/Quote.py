from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class Quote:
    def __init__(self, depot_id, side, instrument_id, quantity, venue_id):
        self.depot_id = depot_id
        self.side = side
        self.instrument_id = instrument_id
        self.quantity = quantity
        self.venue_id = venue_id

    def __str__(self):
        return f'''
        {{"depotId": "{self.depot_id}", 
        "orderType": "QUOTE",
        "side": "{self.side}", 
        "instrumentId": "{self.instrument_id}",
        "quantity": {{"value": "{self.quantity}", "unit": "XXX"}},
        "venueId": "{self.venue_id}"
        }}'''

    def validation_quote_body(self, quote_uuid, quote_ticket_uuid, quote_price, quote_time_stamp):
        return f'''
            {{"depotId": "{self.depot_id}",
            "orderType": "QUOTE", "side": "{self.side}", 
            "instrumentId": "{self.instrument_id}",
            "quantity": {{"value": "{self.quantity}", "unit": "XXX"}},
            "venueId": "{self.venue_id}",
            "quoteId": "{quote_uuid}",
            "quoteTicketId": "{quote_ticket_uuid}",
            "limit": {{"value": "{quote_price['value']}", "unit": "EUR"}},
            "creationTimestamp": "{quote_time_stamp}"
            }}'''
