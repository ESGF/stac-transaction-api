import json
from parse import parse


class API:
    def __init__(self):
        self.routes = {}

    def __call__(self, event, context):
        return self.handle_request(event)

    def response(self, status_code, body):
        return {
            "statusCode": status_code,
            "body": json.dumps(body),
        }

    def find_handler(self, request_path):
        for path, handler in self.routes.items():
            parse_result = parse(path, request_path)
            if parse_result is not None:
                return handler, parse_result.named
        return None, None

    def handle_request(self, event):
        request_path = event.get("path")
        handler, kwargs = self.find_handler(request_path)
        if handler is None:
            return self.response(404, {"error": "Not found"})
        return handler(event, **kwargs)

    def route(self, path):
        def wrapper(route_handler):
            def handler(event, **kwargs):
                authorizer = event.get("requestContext").get("authorizer")
                access_token_json_string = authorizer.get("access_token")
                groups_json_string = authorizer.get("groups")
                body_json_string = event.get("body")

                # log json strings to the api's CloudWatch logs (they are formatted nicer than dictionaries)
                print(access_token_json_string)
                print(groups_json_string)

                access_token = json.loads(access_token_json_string)
                groups = json.loads(groups_json_string)
                try:
                    body = json.loads(body_json_string) if body_json_string else None
                except json.JSONDecodeError:
                    return self.response(400, {"error": "Invalid JSON in request body"})
                return route_handler(event, access_token, groups, body, **kwargs)

            self.routes[f"{path}"] = handler
            return handler

        return wrapper


api = API()
