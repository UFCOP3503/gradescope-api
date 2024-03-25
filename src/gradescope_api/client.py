from time import time
from typing import Any, Optional
from bs4 import BeautifulSoup
import aiohttp
from gradescope_api.course import GradescopeCourse

from gradescope_api.errors import check_response
from gradescope_api.utils import get_url_id

USER_AGENT = "gradescope-api"
BASE_URL = "https://www.gradescope.com"


class GradescopeClient:

    # These will mostly be None for security purposes
    email: str | None
    password: str | None

    def __init__(self, email: str, password: str) -> None:
        self.session = aiohttp.ClientSession()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.email = email
        self.password = password

    async def setup(self):
        if self.email is None or self.password is None:
            raise ValueError("Email and password must be provided to log in.")
        await self._log_in(email=self.email, password=self.password)
        self.password = None

    async def shutdown(self):
        await self.session.close()

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.shutdown()

    def get_base_url(self) -> str:
        return BASE_URL

    async def _get_token(
        self, url: str, action: Optional[Any] = None, meta: Optional[Any] = None, content: Optional[Any] = None
    ) -> str:
        """
        Return the Gradescope authenticity token.
        """
        if not content:
            response = await self.session.get(url, timeout=20)
            content = await response.read()

        soup = BeautifulSoup(content, "html.parser")
        form = None
        if action:
            form = soup.find("form", {"action": action})
        elif meta:
            return soup.find("meta", {"name": meta})["content"]
        else:
            form = soup.find("form")

        return form.find("input", {"name": "authenticity_token"})["value"]

    async def submit_form(
        self,
        url: str,
        referer_url: Optional[str] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        header_token: Optional[Any] = None,
        json: Optional[Any] = None,
    ) -> aiohttp.ClientResponse:
        if not referer_url:
            referer_url = url
        headers = {"Host": "www.gradescope.com", "Origin": "https://www.gradescope.com", "Referer": referer_url}
        if header_token is not None:
            headers["X-CSRF-Token"] = header_token
        if files:
            raise NotImplementedError("File uploads are not yet supported.")
        return await self.session.post(url, data=data, json=json, headers=headers, timeout=20)

    async def _log_in(self, email: str, password: str):
        url = BASE_URL + "/login"
        token = await self._get_token(url)
        payload = {
            "utf8": "✓",
            "authenticity_token": token,
            "session[email]": email,
            "session[password]": password,
            "session[remember_me]": 1,
            "commit": "Log In",
            "session[remember_me_sso]": 0,
        }
        response = await self.submit_form(url=url, data=payload)
        await check_response(response, error="failed to log in")

    def get_course(self, course_url: Optional[str] = None, course_id: Optional[str] = None):
        course_id = course_id or get_url_id(course_url, "courses")
        return GradescopeCourse(_client=self, course_id=course_id)
