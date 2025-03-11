import git
import toml
from packaging import version


def check_origin_tag_status(origin_metadata):
    """
    Check if the tag in metadata matches the latest tag in the original repository
    using gitpython's ls_remote
    """
    result = {
        "current_tag": origin_metadata["tag"],
        "needs_update": False,
        "latest_tag": None,
    }

    try:
        # Get all remote tags using ls_remote
        refs = (
            git.cmd.Git().ls_remote("--tags", origin_metadata["repo_url"]).split("\n")
        )

        # Process the refs to get tag names
        tags = []
        for ref in refs:
            if ref:
                hash_ref = ref.split()
                if len(hash_ref) == 2:  # Ensure we have both hash and ref
                    tag = hash_ref[1].replace("refs/tags/", "")
                    # Skip tags with ^{} (dereferenced tags)
                    if not tag.endswith("^{}"):
                        tags.append(tag)

        if not tags:
            result["error"] = "No tags found in repository"
            return result

        # Sort tags by version
        sorted_tags = sorted(tags, key=lambda t: version.parse(t.lstrip("v")))
        latest_tag = sorted_tags[-1]
        result["latest_tag"] = latest_tag

        # Compare versions
        current_version = version.parse(origin_metadata["tag"].lstrip("v"))
        latest_version = version.parse(latest_tag.lstrip("v"))

        result["needs_update"] = current_version < latest_version

    except git.exc.GitCommandError as e:
        result["error"] = f"Git command error: {str(e)}"
    except Exception as e:
        result["error"] = f"Error checking version status: {str(e)}"

    return result


def load_metadata():
    """Load metadata from .thothctl.toml file"""
    try:
        metadata = toml.load(".thothctl.toml")
        return metadata.get("origin_metadata", {})
    except Exception as e:
        raise Exception(f"Error loading .thothctl.toml: {str(e)}")


# Example usage
try:
    # Load metadata from .thothctl.toml
    origin_metadata = load_metadata()

    # Check version status
    result = check_origin_tag_status(origin_metadata)

    # Print results
    if result.get("error"):
        print(f"Error: {result['error']}")
    elif result.get("needs_update"):
        print(
            f"Update needed! Current version {result['current_tag']} is behind latest version {result['latest_tag']}"
        )
    else:
        print(f"You are using the latest version: {result['current_tag']}")

except Exception as e:
    print(f"Error: {str(e)}")
