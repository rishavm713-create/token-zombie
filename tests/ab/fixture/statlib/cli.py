import argparse, sys
from statlib import stats, io_utils, formatting


def summarize(xs):
    return {"mean": stats.mean(xs), "median": stats.median(xs), "stdev": stats.stdev(xs), "p90": stats.percentile(xs, 90)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="statlib")
    ap.add_argument("path")
    a = ap.parse_args(argv)
    print(formatting.format_text(summarize(io_utils.read_numbers(a.path))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
