import os
import json
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("path")


def main(args):
    runners = {}

    for filename in os.listdir(args.path):
        with open(os.path.join(args.path, filename)) as file:
            runners[filename.removesuffix(".json")] = json.load(file)

    all_versions = list(
        {
            version
            for version_list in runners.values()
            for version in version_list
        }
    )

    print(
        json.dumps(
            {
                "runner": list(runners),
                "python-version": all_versions,
                "exclude": [
                    {"runner": runner, "python-version": version}
                    for version in all_versions
                    for runner, version_list in runners.items()
                    if version not in version_list
                ],
            }
        )
    )


if __name__ == "__main__":
    main(parser.parse_args())
