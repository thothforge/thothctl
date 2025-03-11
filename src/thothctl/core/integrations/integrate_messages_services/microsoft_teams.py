# adapters/teams_notifier.py
import pymsteams

from ....config.models import ReportStatus, ScanResult


class TeamsNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_scan_result(self, result: ScanResult, in_pipeline: bool = False):
        card = pymsteams.connectorcard(self.webhook_url)
        card.title("Terraform Compliance Report")
        card.color("7b9683")

        # Add test results section
        tests_section = pymsteams.cardsection()
        tests_section.title("Tests")
        tests_section.text(str(result.total_tests))

        # Add failures section
        fails_section = pymsteams.cardsection()
        fails_section.title("Failures")
        fails_section.text(str(result.failures))

        # Add result section with appropriate image
        result_section = pymsteams.cardsection()
        result_section.title("Result")
        result_section.text(result.message)

        self._add_status_image(result_section, result.status)

        card.addSection(tests_section)
        card.addSection(fails_section)
        card.addSection(result_section)

        card.send()

    def _add_status_image(self, section: pymsteams.cardsection, status: ReportStatus):
        images = {
            ReportStatus.APPROVED: "https://support.content.office.net/en-us/media/773afccb-4687-4b9f-8a89-8b32f640b27d.png",
            ReportStatus.SKIPPED: "https://support.content.office.net/en-us/media/47588200-0bf0-46e9-977e-e668978f459c.png",
            ReportStatus.FAILED: "https://support.content.office.net/en-us/media/6b8c0bff-7ddc-4bff-9101-8360f8c8a727.png",
        }
        section.activityImage(images[status])
