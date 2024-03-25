import asyncio
import os

from dotenv import load_dotenv
from gradescope_api.client import GradescopeClient

load_dotenv()


async def main():
    client = GradescopeClient(
        email=os.environ["GS_EMAIL"], password=os.environ["GS_PASSWORD"],
    )
    async with client:
        course = client.get_course(
            course_url="https://www.gradescope.com/courses/735697/",
        )
        print(await course.get_assignments())
        assignment = course.get_assignment(
            assignment_url="https://www.gradescope.com/courses/735697/assignments/4191897/review_grades",
        )
        if assignment:
            await assignment.apply_extension("abigail@cbrxyz.com", 1)
        else:
            print("No assignment found!")


asyncio.run(main())
