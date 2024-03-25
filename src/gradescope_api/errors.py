from aiohttp import ClientResponse


class GradescopeAPIError(Exception):
    pass


class AuthError(GradescopeAPIError):
    pass


class RequestError(GradescopeAPIError):
    pass


async def check_response(response: ClientResponse, error: str):
    if not response.ok:
        raise RequestError(
            "An error occurred in a request to Gradescope servers. Details: "
            + "\n"
            + "Status Code: "
            + str(response.status)
            + "\n"
            + "Error: "
            + str(error)
            + "\n"
            "Request: "
            + str(response.request_info)
            + "\n"
            + "Response: "
            + str(await response.content.read()),
        )
