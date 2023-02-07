import os
import sys
import json
import logging
import pprint

def get_nested_value(dictionary, key):
    """This function reads the data from the FIO JSON file based on the supplied
    key (which is often a nested path within the JSON file).
    """
    if not key:
        return None
    for item in key:
        dictionary = dictionary[item]
    return dictionary


def check_for_steadystate(record, mode):
    keys = record["jobs"][0].keys()
    if "steadystate" in keys:
        return True
    else:
        return False


def walk_dictionary(dictionary, path):
    result = dictionary
    for item in path:
        result = result[item]
    return result


def validate_job_option_key(dataset, key):
    mykeys = dataset['jobs'][0]['job options'].keys()
    if key in mykeys:
        return True
    else:
        raise KeyError


def validate_job_options(record, key):
    # Job options can either be in the job or in global options.
    # Sometimes some options are in one and others in the other.
    # We need to figure out which one.

    
    jobOptionsRaw = ["jobs", 0, "job options"]
    try:
        walk_dictionary(record, jobOptionsRaw)
        validate_job_option_key(record, key)
        return jobOptionsRaw
    except KeyError:
        return ['global options']


def validate_number_of_jobs(record):
    length = len(record['jobs'])
    if length > 1:
        print(f"\n Unfortunately, fio-plot can't deal (yet) with JSON files containing multiple ({length}) jobs\n")
        print("See also: https://github.com/louwrentius/fio-plot/issues/64")
        sys.exit(1)


def get_json_mapping(mode, dataset):
    """This function contains a hard-coded mapping of FIO nested JSON data
    to a flat dictionary.
    """
    validate_number_of_jobs(dataset)
    root = ["jobs", 0]
    jobOptions = validate_job_options(dataset, "numjobs")
    data = root + [mode]
    dictionary = {
        "fio_version": ["fio version"],
        "iodepth": (validate_job_options(dataset, "iodepth") + ["iodepth"]),
        "numjobs": (validate_job_options(dataset, "numjobs") + ["numjobs"]),
        "bs": (validate_job_options(dataset, "bs") + ["bs"]),
        "rw": (validate_job_options(dataset, "rw") + ["rw"]),
        "bw": (data + ["bw"]),
        "iops": (data + ["iops"]),
        "iops_stddev": (data + ["iops_stddev"]),
        "lat_ns": (data + ["lat_ns", "mean"]),
        "lat_stddev": (data + ["lat_ns", "stddev"]),
        "latency_ms": (root + ["latency_ms"]),
        "latency_us": (root + ["latency_us"]),
        "latency_ns": (root + ["latency_ns"]),
        "cpu_usr": (root + ["usr_cpu"]),
        "cpu_sys": (root + ["sys_cpu"])
    }

    # This is hideous, terrible code, I know.
    if check_for_steadystate(dataset, mode):
        dictionary["ss_attained"] = root + ["steadystate"] + ["attained"]
        dictionary["ss_settings"] = ["global options"] + ["steadystate"]
        dictionary["ss_data_bw_mean"] = root + ["steadystate"] + ["data"] + ["bw_mean"]
        dictionary["ss_data_iops_mean"] = (
                root + ["steadystate"] + ["data"] + ["iops_mean"]
        )

    else:
        dictionary["ss_attained"] = None
        dictionary["ss_settings"] = None
        dictionary["ss_data_bw_mean"] = None
        dictionary["ss_data_iops_mean"] = None

    return dictionary

def printkeys(data, depth=0, maxdepth=3):
    """
    For debugging only
    """
    if depth <= maxdepth:
        if isinstance(data, dict):
            for key,value in data.items():
                print(f"{'-' * depth} {key}")
                printkeys(value, depth+1)
        elif isinstance(data, list):
            for item in data:
                printkeys(item, depth+1)

def validate_json_data(settings, record):
    options = validate_job_options(record, "numjobs")
    result = {"mode": None, "mapping": None}
    if settings["rw"] == "randrw":
        mode = settings["filter"][0]
    elif settings["rw"] == "read" or settings["rw"] == "write":
        mode = settings["rw"]
    elif settings["rw"] == "rw":
        mode = settings['filter'][0]
    elif settings["rw"] == "readwrite":
        mode = settings['filter'][0]
    else:
        mode = get_nested_value(record, options + ["rw"])[4:]
    result["mode"] = mode
    result["mapping"] = get_json_mapping(mode, record)
    return result

def build_json_mapping(settings, dataset):
    """
    This funcion traverses the relevant JSON structure to gather data
    and store it in a flat dictionary. We do this for each imported json file.
    """
    for item in dataset:
        item["data"] = []
        # printkeys(item["rawdata"]) # for debugging
        for record in item["rawdata"]:
            result = validate_json_data(settings, record)
            mode = result["mode"]
            m = result["mapping"]
            row = {
                "iodepth": int(get_nested_value(record, m["iodepth"])),
                "numjobs": int(get_nested_value(record, m["numjobs"])),
                "bs": get_nested_value(record, m["bs"]),
                "rw": get_nested_value(record, m["rw"]),
                "iops": get_nested_value(record, m["iops"]),
                "iops_stddev": get_nested_value(record, m["iops_stddev"]),
                "lat": get_nested_value(record, m["lat_ns"]),
                "lat_stddev": get_nested_value(record, m["lat_stddev"]),
                "latency_ms": get_nested_value(record, m["latency_ms"]),
                "latency_us": get_nested_value(record, m["latency_us"]),
                "latency_ns": get_nested_value(record, m["latency_ns"]),
                "bw": get_nested_value(record, m["bw"]),
                "type": mode,
                "cpu_sys": get_nested_value(record, m["cpu_sys"]),
                "cpu_usr": get_nested_value(record, m["cpu_usr"]),
                "ss_attained": get_nested_value(record, m["ss_attained"]),
                "ss_data_bw_mean": get_nested_value(record, m["ss_data_bw_mean"]),
                "ss_data_iops_mean": get_nested_value(record, m["ss_data_iops_mean"]),
                "ss_settings": get_nested_value(record, m["ss_settings"]),
                "fio_version": get_nested_value(record, m["fio_version"]),
            }
            item["data"].append(row)
            # item["rawdata"] = None  # --> enable to throw away the data after parsing.
    return dataset

def parse_json_data(settings, dataset):
    dataset = build_json_mapping(settings, dataset)
    return dataset

