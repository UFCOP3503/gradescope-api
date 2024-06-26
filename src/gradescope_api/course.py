from __future__ import annotations

from pytz import timezone
import datetime
import json
from typing import TYPE_CHECKING, Optional

from bs4 import BeautifulSoup

from gradescope_api.assignment import GradescopeAssignment
from gradescope_api.errors import check_response
from gradescope_api.student import GradescopeStudent
from gradescope_api.utils import get_url_id

if TYPE_CHECKING:
    from gradescope_api.client import GradescopeClient


class GradescopeCourse:
    def __init__(self, _client: GradescopeClient, course_id: str) -> None:
        self._client = _client
        self.course_id = course_id
        self.roster: list[GradescopeStudent] = []

    def get_url(self) -> str:
        return self._client.get_base_url() + f"/courses/{self.course_id}"

    async def get_roster(self) -> list[GradescopeStudent]:
        if self.roster:
            return self.roster

        url = self._client.get_base_url() + f"/courses/{self.course_id}/memberships"
        response = await self._client.session.get(url=url, timeout=20)
        await check_response(response, "failed to get roster")

        soup = BeautifulSoup(await response.content.read(), "html.parser")
        for row in soup.find_all("tr", class_="rosterRow"):
            nameButton = row.find("button", class_="js-rosterName")
            role = row.find("option", selected=True).text
            if nameButton and role == "Student":
                user_id = nameButton["data-url"].split("?user_id=")[1]
                editButton = row.find("button", class_="rosterCell--editIcon")
                if editButton:
                    data_email = editButton["data-email"]
                    data_cm: dict = json.loads(editButton["data-cm"])
                    self.roster.append(
                        GradescopeStudent(
                            _client=self._client,
                            user_id=user_id,
                            full_name=data_cm.get("full_name"),
                            first_name=data_cm.get("first_name"),
                            last_name=data_cm.get("last_name"),
                            sid=data_cm.get("sid"),
                            email=data_email,
                        ),
                    )

        return self.roster

    async def get_assignments(self) -> list[GradescopeAssignment]:
        url = self.get_url() + "/assignments"
        response = await self._client.session.get(url=url, timeout=20)
        await check_response(response, "failed to get assignments")

        soup = BeautifulSoup(await response.content.read(), "html.parser")
        props = soup.find("div", {"data-react-class": "AssignmentsTable"})[
            "data-react-props"
        ]
        data = json.loads(props)
        assignments = []
        for row in data.get("table_data", []):
            id = (
                str(row["id"][row["id"].rfind("_") + 1 :])
                if "id" in row and "_" in row["id"]
                else ""
            )
            # Due date is a iso string in EST timezone
            due_date = (
                datetime.datetime.fromisoformat(
                    row["submission_window"]["due_date"],
                ).replace(tzinfo=timezone("US/Eastern"))
                if "submission_window" in row
                and "due_date" in row["submission_window"]
                and isinstance(row["submission_window"]["due_date"], str)
                else None
            )
            assignments.append(
                GradescopeAssignment(
                    _client=self._client,
                    _course=self,
                    assignment_id=id,
                    title=row["title"],
                    due_date=due_date,
                ),
            )

        return assignments

    async def get_student(
        self,
        sid: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[GradescopeStudent]:
        assert sid or email
        roster = await self.get_roster()
        for student in roster:
            if sid is not None and student.sid == sid:
                return student
            if email is not None and student.email == email:
                return student
        return None

    def get_assignment(
        self,
        assignment_id: Optional[str] = None,
        assignment_url: Optional[str] = None,
    ) -> Optional[GradescopeAssignment]:
        assert assignment_id or assignment_url
        assignment_id = assignment_id or get_url_id(
            url=assignment_url,
            kind="assignments",
        )
        return GradescopeAssignment(
            _client=self._client,
            _course=self,
            assignment_id=assignment_id,
        )
