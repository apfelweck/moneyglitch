import datetime
import json
import yaml
import requests
import uuid
import time

from order_types.Quote import Quote


class Session:

    def __init__(self, properties_file, access_file):
        self.properties_file = properties_file
        self.access_file = access_file

        with open(properties_file, 'r') as file:
            self.props = yaml.safe_load(file)
            self.url = self.props['url']
            self.oauth_url = self.props['oauth_url']

            if any(key is None for key in self.props.values()):
                raise ValueError(f'You must provide account information in {properties_file} file')

        with open(access_file, 'r') as file:
            self.access = yaml.safe_load(file)
            self.session_id = self.access['session_id']
            self.access_token = self.access['access_token']
            self.refresh_token = self.access['refresh_token']
            if self.access['activate_session_timestamp'] is not None:
                self.activate_session_timestamp = datetime.datetime.strptime(
                    str(self.access['activate_session_timestamp']), "%Y-%m-%d %H:%M:%S.%f")
            else:
                self.activate_session_timestamp = datetime.datetime.now()

        self.process_status(self.get_session_status())
        self.refresh_session_tan()
        # from now on we have an active Session-Tan
        self.depot_id = self.get_depot_id().json()['values'][0]['depotId']

    def refresh_session_tan(self):
        if (datetime.datetime.now() - self.activate_session_timestamp).total_seconds() <= 400:
            return
        print('refreshing session')
        response = requests.post(
            f'{self.oauth_url}/oauth/token',
            allow_redirects=False,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "client_id": self.props['client_id'],
                "client_secret": self.props['client_secret'],
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            })
        if response.status_code == 200:
            self.access_token = response.json()['access_token']
            self.refresh_token = response.json()['refresh_token']
            self.activate_session_timestamp = datetime.datetime.now()

            self.write_to_access_file()
        else:
            raise RuntimeError(
                f'Error in refresh_session_tan. status_code = {response.status_code} text = {response.text}')

    def write_to_access_file(self):
        access = {
            "access_token": self.access_token,
            "session_id": self.session_id,
            "refresh_token": self.refresh_token,
            "activate_session_timestamp": self.activate_session_timestamp
        }
        with open(self.access_file, 'w') as file:
            yaml.dump(access, file, default_flow_style=False)

    def tan_session(self):
        # 2.1 OAuth2 Resource Owner Password Credentials Flow
        response = requests.post(
            f"{self.oauth_url}/oauth/token",
            data={
                "client_id": self.props['client_id'],
                "client_secret": self.props['client_secret'],
                "username": self.props['username'],
                "password": self.props['pin'],
                "grant_type": "password"
            },
            allow_redirects=False,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            })
        json_response = response.json()
        if json_response == {'error': 'invalid_client', 'error_description': 'Bad client credentials'}:
            raise ValueError(f'Invalid credentials provided in {self.access_file}')

        self.access_token = json_response["access_token"]
        self.refresh_token = json_response["refresh_token"]

        # 2.2 Session-Status
        self.session_id = uuid.uuid4()
        response = requests.get(
            f'{self.url}/session/clients/user/v1/sessions',
            allow_redirects=False,
            headers=self.get_basic_header())
        self.session_id = response.json()[0]['identifier']

        # 2.3 Anlage Validierung einer Session-TAN
        response = requests.post(
            f'{self.url}/session/clients/user/v1/sessions/{self.session_id}/validate',
            data=f'{{"identifier":"{self.session_id}","sessionTanActive":true,"activated2FA":true}}',
            allow_redirects=False,
            headers=self.get_basic_header())
        challenge_id = json.loads(response.headers["x-once-authentication-info"])["id"]

        input("Press enter when you completed the tan...\n")

        # 2.4 Aktivierung einer Session-TAN
        requests.patch(
            f'{self.url}/session/clients/user/v1/sessions/{self.session_id}',
            data=f'{{"identifier":"{self.session_id}","sessionTanActive":true,"activated2FA":true}}',
            allow_redirects=False,
            headers=self.get_challenge_header(challenge_id))

        # 2.5 OAuth2 CD Secondary-Flow
        response = requests.post(
            f"{self.oauth_url}/oauth/token",
            data={
                "client_id": self.props['client_id'],
                "client_secret": self.props['client_secret'],
                "token": self.access_token,
                "grant_type": "cd_secondary"
            },
            allow_redirects=False,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            })
        self.access_token = response.json()['access_token']
        self.refresh_token = response.json()['refresh_token']
        self.activate_session_timestamp = datetime.datetime.now()
        self.write_to_access_file()

    def process_status(self, status_response):
        if status_response.status_code == 200:
            temp = status_response.json()[0]
            if temp['sessionTanActive'] and temp['activated2FA']:
                print("Tan-Session still active")
                return
        elif status_response.status_code == 401:
            temp = status_response.json()
            if temp['summary'] == "error=401, error_description=unauthorized":
                print("Tan abgelaufen. Neue Tan wird angefragt...")
                self.tan_session()
                return
        raise RuntimeError(
            f'Error while requesting status. status_code = {status_response.status_code} text = {status_response.text}')

    def get_session_status(self):
        response = requests.get(
            f'{self.url}/session/clients/user/v1/sessions',
            allow_redirects=False,
            headers=self.get_basic_header())
        return response

    def get_account_balance(self):
        response = requests.get(
            f'{self.url}/banking/clients/user/v2/accounts/balances',
            allow_redirects=False,
            headers=self.get_basic_header())
        return response

    def get_depot_id(self):
        response = requests.get(
            f'{self.url}/brokerage/clients/user/v3/depots',
            allow_redirects=False,
            headers=self.get_basic_header())
        return response

    def get_order_dimensions(self, wkn):
        response = requests.get(
            f'{self.url}/brokerage/v3/orders/dimensions',
            allow_redirects=False,
            headers=self.get_basic_header(),
            params={
                "WKN": {wkn},
                "type": "EXCHANGE"})
        return response

    def get_basic_header(self):
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "x-http-request-info": f'{{"clientRequestId":{{"sessionId":"{self.session_id}",'
                                   f'"requestId":"{time.time()}"}}}}',
            "Content-Type": "application/json"
        }

    def get_challenge_header(self, challenge_id):
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "x-http-request-info": f'{{"clientRequestId":{{"sessionId":"{self.session_id}",'
                                   f'"requestId":"{time.time()}"}}}}',
            "Content-Type": "application/json",
            "x-once-authentication-info": f'{{"id":"{challenge_id}"}}',
            "x-once-authentication": "TAN_FREI"
        }

    def create_order_data(self, instrument_id, venue_id, side, limit_price, quantity):
        return f'''{{
                "depotId": "{self.depot_id}", 
                "orderType": "LIMIT", 
                "side": "{side}", 
                "instrumentId": "{instrument_id}",
                "quantity": {{"value": "{quantity}", "unit": "XXX"}},
                "venueId": "{venue_id}",
                "limit": {{"value": "{limit_price}", "unit": "EUR"}},
                "validityType": "GFD"
                }}'''

    def get_existing_orders(self):
        response = requests.get(
            f'{self.url}/brokerage/depots/{self.depot_id}/v3/orders',
            headers=self.get_basic_header(),
            allow_redirects=False)
        return response

    def get_instrument(self, instrument_id):
        response = requests.get(
            f'{self.url}/brokerage/v1/instruments/{instrument_id}',
            allow_redirects=False,
            headers=self.get_basic_header(),
            params={

            })
        return response.json()

    # Order -------------------------------------------------------------------

    def pre_validation_order(self, data):
        response = requests.post(
            f'{self.url}/brokerage/v3/orders/prevalidation',
            allow_redirects=False,
            headers=self.get_basic_header(),
            data=data)
        return response

    def validate_order(self, data):
        response = requests.post(
            f'{self.url}/brokerage/v3/orders/validation',
            headers=self.get_basic_header(),
            allow_redirects=False,
            data=data)

        if response.status_code == 201:
            order_Tan = json.loads(response.headers.get('x-once-authentication-info'))['id']
            return response.json(), order_Tan
        else:
            raise RuntimeError(
                f'Error in validate_order. status_code = {response.status_code} text = {response.content}')

    def ex_ante_cost_oder(self, data):
        response = requests.post(
            f'{self.url}/brokerage/v3/orders/costindicationexante',
            allow_redirects=False,
            headers=self.get_basic_header(),
            data=data)
        if response.status_code == 201:
            return response.json()
        else:
            raise RuntimeError(
                f'Error in ex_ante_cost_oder. status_code = {response.status_code} text = {response.content}')

    def activate_order(self, data, challenge_id):
        response = requests.post(
            f'{self.url}/brokerage/v3/orders',
            allow_redirects=False,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
                "x-http-request-info": f'{{"clientRequestId":{{"sessionId":"{self.session_id}",'
                                       f'"requestId":"{time.time()}"}}}}',
                "Content-Type": "application/json",
                "x-once-authentication-info": f'{{"id":"{challenge_id}"}}',
                "x-once-authentication": "TAN_FREI"
            },
            data=data)
        if response.status_code == 201:
            return response.json()
        else:
            raise RuntimeError(
                f'Error in activate_order. status_code = {response.status_code} text = {response.content}')

    # Quote -------------------------------------------------------------------

    def create_quote_request_initialization(self, quote: Quote):
        response = requests.post(
            f'{self.url}/brokerage/v3/quoteticket',
            allow_redirects=False,
            headers=self.get_basic_header(),
            data=quote.__str__())
        if response.status_code == 201:
            quote_ticket_uuid = response.json()['quoteTicketId']
            challenge_id = json.loads(response.headers.get("x-once-authentication-info"))['id']
            return quote_ticket_uuid, challenge_id
        else:
            raise RuntimeError(
                f'Error in create_quote_request_initialization. status_code = {response.status_code} text = {response.content}')

    def update_quote_request_initialization_with_tan(self, quote_ticket_uuid, challenge_id):
        response = requests.patch(
            f'{self.url}/brokerage/v3/quoteticket/{quote_ticket_uuid}',
            allow_redirects=False,
            headers=self.get_challenge_header(challenge_id))
        if response.status_code != 204:
            raise RuntimeError(
                f'Error in update_quote_request_initialization_with_tan. status_code = {response.status_code} text = {response.content}')

    def create_quote_request(self, quote: Quote):
        response = requests.post(
            f'{self.url}/brokerage/v3/quotes',
            allow_redirects=False,
            headers=self.get_basic_header(),
            data=quote.__str__()
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code == 422 and response.json()['messages'][0]['key'].startswith(
                "fehler-keine-handelswerte"):
            return {"error": "fehler-keine-handelswerte"}
        else:
            raise RuntimeError(
                f'Error in create_quote_request. status_code = {response.status_code} text = {response.content}')

    def validate_quote_order(self, quote: Quote, quote_uuid, quote_ticket_uuid, quote_price, quote_timestamp):
        response = requests.post(
            f'{self.url}/brokerage/v3/orders/validation',
            allow_redirects=False,
            headers=self.get_basic_header(),
            data=quote.validation_quote_body(quote_uuid, quote_ticket_uuid, quote_price, quote_timestamp))
        if response.status_code == 201:
            challenge_id = json.loads(response.headers.get("x-once-authentication-info"))['id']
            return challenge_id
        else:
            raise RuntimeError(
                f'Error in validate_quoute_order. status_code = {response.status_code} text = {response.content}')

    def activate_quote_order(self, quote: Quote, quote_uuid, quote_ticket_uuid, quote_price, quote_timestamp,
                             challenge_id):
        response = requests.post(
            f'{self.url}/brokerage/v3/orders',
            allow_redirects=False,
            headers=self.get_challenge_header(challenge_id),
            data=quote.validation_quote_body(quote_uuid, quote_ticket_uuid, quote_price, quote_timestamp))
        if response.status_code == 201:
            return response.json()
        else:
            raise RuntimeError(
                f'Error in activate_quote_order. status_code = {response.status_code} text = {response.content}')

    # ------------------------------------------------------------------------
