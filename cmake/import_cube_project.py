#!/usr/bin/env python3
"""Read the checked-in CubeIDE source selection without running the IDE.

The two builds share the linked resources, exclusions, include paths, defines,
and per-file optimization levels. Physical source folders are scanned as CDT
does; virtual folders contribute only their explicitly linked files.
"""

import argparse
import fnmatch
import re
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET


SOURCE_SUFFIXES = {".c", ".cpp", ".s", ".S"}


def quote(value):
    return f"[==[{value}]==]"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    repo = project.parents[2]
    description = ET.parse(project / ".project").getroot()
    variables = {item.findtext("name"): item.findtext("value")
                 for item in description.findall("variableList/variable")}

    def resolve(uri):
        uri = unquote(uri)
        head, _, tail = uri.partition("/")
        if head.startswith("${") and head.endswith("}"):
            head = head[2:-1]
        parent = re.fullmatch(r"PARENT-(\d+)-PROJECT_LOC", head)
        if parent:
            base = project.parents[int(parent[1]) - 1]
        elif head == "PROJECT_LOC":
            base = project
        elif head in variables:
            base = resolve(variables[head])
        else:
            raise ValueError(f"Unsupported project location: {uri}")
        return (base / tail).resolve()

    files = {}
    directories = {}
    for link in description.findall("linkedResources/link"):
        name = link.findtext("name")
        uri = link.findtext("locationURI", "")
        if uri.startswith("virtual:"):
            continue
        if link.findtext("type") == "1":
            if Path(name).suffix in SOURCE_SUFFIXES:
                files[name] = resolve(uri)
        elif link.findtext("type") == "2":
            directories[name] = resolve(uri)

    configs = ET.parse(project / ".cproject").getroot().findall(".//configuration")
    config = next(item for item in configs if item.get("name") == "Debug-STM32U5A5")
    sources = {}
    scan_roots = []
    for entry in config.findall("sourceEntries/entry"):
        name = entry.get("name")
        excluded = entry.get("excluding", "").split("|")

        def selected(logical):
            relative = logical[len(name) + 1:]
            return not any(pattern and (fnmatch.fnmatchcase(relative, pattern)
                       or relative.startswith(pattern.rstrip("/") + "/"))
                       for pattern in excluded)

        folder = directories.get(name, project / name)
        if folder.is_dir():
            scan_roots.append(folder)
            for source in sorted(folder.rglob("*")):
                if source.is_file() and source.suffix in SOURCE_SUFFIXES:
                    logical = f"{name}/{source.relative_to(folder).as_posix()}"
                    if selected(logical):
                        sources[logical] = source.resolve()
        for logical, source in sorted(files.items()):
            if logical.startswith(name + "/") and selected(logical):
                if not source.is_file():
                    raise FileNotFoundError(f"Linked source is missing: {logical}: {source}")
                sources[logical] = source

    output = ["# Generated from .project and .cproject; do not edit."]

    def emit(name, values):
        output.append(f"set({name}\n" + "\n".join(f"  {quote(value)}" for value in values) + "\n)")

    emit("UNA_CUBE_SOURCES", dict.fromkeys(str(path) for path in sources.values()))
    emit("UNA_CUBE_SCAN_ROOTS", map(str, scan_roots))
    tools = config.findall("folderInfo/toolChain/tool")
    for language, tool_name in (("C", "MCU/MPU GCC Compiler"),
                                ("CXX", "MCU/MPU G++ Compiler")):
        tool = next(tool for tool in tools if tool.get("name") == tool_name)
        options = {option.get("name"): option for option in tool.findall("option")}
        includes = []
        for value in options["Include paths (-I)"].findall("listOptionValue"):
            path = value.get("value").strip('"').replace("${UNA_SDK}", str(repo / "SDK"))
            includes.append(str((project / "Debug-STM32U5A5" / path).resolve()))
        emit(f"UNA_CUBE_{language}_INCLUDES", dict.fromkeys(includes))
        defines = [value.get("value") for value in options["Define symbols (-D)"].findall("listOptionValue")]
        emit(f"UNA_CUBE_{language}_DEFINES", [value for value in defines
             if not value.startswith(("BUILD_VERSION=", "PROJECT_NAME="))])

    for info in config.findall("fileInfo"):
        source = sources.get(info.get("resourcePath"))
        if source is None:
            continue
        for option in info.findall(".//option"):
            if option.get("name") == "Optimization level":
                level = option.get("value").rsplit(".", 1)[1]
                flag = {"o0": "-O0", "og": "-Og", "os": "-Os"}[level]
                output.append(f"set_source_files_properties({quote(source)} PROPERTIES COMPILE_OPTIONS {quote(flag)})")

    args.output.write_text("\n".join(output) + "\n")
    print(f"Imported {len(set(sources.values()))} C/C++/assembly sources from Debug-STM32U5A5")


if __name__ == "__main__":
    main()
