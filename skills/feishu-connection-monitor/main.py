import argparse

from gateway_http_server import run_server
from monitor import ConfigManager, ConnectionMonitor, JsonlLogger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=["monitor", "gateway-server"], default="monitor")
    args = parser.parse_args()
    if args.mode == "gateway-server":
        run_server(args.config)
        return
    config_manager = ConfigManager(args.config)
    config = config_manager.load_if_changed()
    logger = JsonlLogger(config.log_dir)
    monitor = ConnectionMonitor(config_manager=config_manager, logger=logger)
    monitor.run_forever()


if __name__ == "__main__":
    main()
