"""Load hcl2 file to get backend."""
import hcl2


def load_backend(file_hcl: str) -> dict:
    """
    Read HCL file to get backend according to structure.

    :param file_hcl:
    """
    with open(file_hcl, "r", encoding="utf-8") as file:
        data = hcl2.load(file)

        value = {
            "backend_profile": data["locals"]["backend_profile"],
            "bucket": data["locals"]["backend_bucket_name"],
            "path": f'{data["locals"]["provider"]}/{data["locals"]["client"]}/{data["locals"]["project"]}',
        }
    file.close()
    return value
