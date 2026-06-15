"""
start web UI driver.

usage:
  python start_web_ui.py --user-data-dir /tmp/perplexity-chrome [--port 9222]
"""
import argparse

from perplexity.driver import Driver


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user-data-dir", required=True, help="Chrome user data dir")
    p.add_argument("--port", type=int, default=None, help="remote debugging port (optional)")
    args = p.parse_args()

    driver = Driver()
    driver.run(args.user_data_dir, port=args.port)


if __name__ == "__main__":
    main()
