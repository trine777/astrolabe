"""Astrolabe Docker entrypoint."""
import sys
import time

sys.path.insert(0, "/app/src")


def healthcheck():
    """Quick import check for Docker healthcheck."""
    from xingtu.store import XingkongzuoStore
    print("OK")


def main():
    """Initialize and keep running."""
    from xingtu import XingTuService

    service = XingTuService()
    service.initialize()

    stats = service.get_stats()
    print(f"Astrolabe ready. Stats: {stats}", flush=True)

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    if "--check" in sys.argv:
        healthcheck()
    else:
        main()
