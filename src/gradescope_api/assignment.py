from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

import pytz
from bs4 import BeautifulSoup
from dateutil.parser import parse

from gradescope_api.errors import GradescopeAPIError, check_response

if TYPE_CHECKING:
    from gradescope_api.client import GradescopeClient
    from gradescope_api.course import GradescopeCourse

GRADESCOPE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class GradescopeAssignment:

    _course: GradescopeCourse
    assignment_id: str
    title: str
    due_date: datetime | None

    def __init__(self, _client: GradescopeClient, _course: GradescopeCourse, assignment_id: str, title: str, due_date: datetime | None) -> None:
        self._client = _client
        self._course = _course
        self.assignment_id = assignment_id
        self.title = title
        self.due_date = due_date

    def __str__(self) -> str:
        return f"GradescopeAssignment(_course='{self._course}', assignment_id='{self.assignment_id}', title='{self.title}')"

    __repr__ = __str__

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, GradescopeAssignment):
            return False
        return self.assignment_id == o.assignment_id

    def get_url(self) -> str:
        return self._course.get_url() + f"/assignments/{self.assignment_id}"

    async def apply_extension(self, email: str, amount: timedelta):
        """
        A new method to apply an extension to a Gradescope assignment, given an email and a number of days.
        """
        # First, fetch the extensions page for the assignment, which contains a student roster as well as
        # the due date (and hard due date) for the assignment.
        course_id = self._course.course_id
        assignment_id = self.assignment_id
        response = await self._client.session.get(
            f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/extensions", timeout=20
        )
        await check_response(response, "could not load assignment")

        # Once we fetch the page, parse out the data (students + due dates)
        soup = BeautifulSoup(await response.content.read(), "html.parser")
        props = soup.find(
            "li", {"data-react-class": "AddExtension"})["data-react-props"]
        data = json.loads(props)
        students = {row["email"]: row["id"]
                    for row in data.get("students", [])}
        user_id = students.get(email)
        if not user_id:
            raise GradescopeAPIError("student email not found")

        # A helper method to transform the date
        def transform_date(datestr: str):
            dt = pytz.timezone("US/Eastern").localize(parse(datestr))
            dt = dt + amount
            return dt.astimezone(pytz.utc)

        assignment = data["assignment"]
        new_due_date = transform_date(assignment["due_date"])

        if assignment["hard_due_date"]:
            new_hard_due_date = transform_date(assignment["hard_due_date"])

        # Make the post request to create the extension
        url = self.get_url() + "/extensions"
        headers = {
            "Host": "www.gradescope.com",
            "Origin": "https://www.gradescope.com",
            "Referer": url,
            "X-CSRF-Token": await self._client._get_token(url, meta="csrf-token"),
        }
        payload = {
            "override": {
                "user_id": user_id,
                "settings": {
                    "due_date": {"type": "absolute", "value": new_due_date.strftime(GRADESCOPE_DATETIME_FORMAT)}
                },
            }
        }

        if assignment["hard_due_date"]:
            payload["override"]["settings"]["hard_due_date"] = {
                "type": "absolute",
                        "value": new_hard_due_date.strftime(GRADESCOPE_DATETIME_FORMAT),
            }

        response = await self._client.session.post(
            url, headers=headers, json=payload, timeout=20)
        await check_response(response, "creating an extension failed")

    # deprecated
    async def create_extension(self, user_id: str, due_date: datetime, hard_due_date: Optional[datetime] = None):
        """
        Create an extension for a student for this particular assignment. If a hard due date is not provided,
        the hard due date will be set to the provided due date. This behavior is temporary and should be changed
        to be the later of the current hard due date and the provided due date.
        """
        if hard_due_date:
            assert hard_due_date >= due_date

        url = self.get_url() + "/extensions"
        headers = {
            "Host": "www.gradescope.com",
            "Origin": "https://www.gradescope.com",
            "Referer": url,
            "X-CSRF-Token": await self._client._get_token(url, meta="csrf-token"),
        }
        payload = {
            "override": {
                "user_id": user_id,
                "settings": {
                    "due_date": {"type": "absolute", "value": due_date.strftime(GRADESCOPE_DATETIME_FORMAT)},
                    "hard_due_date": {
                        "type": "absolute",
                        "value": (hard_due_date or due_date).strftime(GRADESCOPE_DATETIME_FORMAT),
                    },
                },
            }
        }

        response = await self._client.session.post(
            url, headers=headers, json=payload, timeout=20)
        await check_response(response, "creating an extension failed")
