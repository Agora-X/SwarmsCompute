import argparse

import torch
from hivemind.utils.logging import get_logger, use_hivemind_log_handler
from tqdm.auto import trange

from src.bloom.block import BloomBlock
from src.bloom.model import DistributedBloomConfig
from src.bloom.ops import build_alibi_tensor

use_hivemind_log_handler("in_root_logger")
logger = get_logger(__file__)


def print_device_info(device=None):
    """Prints device stats. Code from https://stackoverflow.com/a/53374933/12891528"""
    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    logger.info(f"Using device: {device}")

    # Additional Info when using cuda
    if device.type == "cuda":
        logger.info(torch.cuda.get_device_name(0))
        logger.info(f"Memory Usage:")
        logger.info(f"Allocated: {round(torch.cuda.memory_allocated(0) / 1024 ** 3, 1)} GB")
        logger.info(f"Cached:   {round(torch.cuda.memory_cached(0) / 1024 ** 3, 1)} GB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single bloom block locally on dummy data")
    parser.add_argument("--config", required=True, type=str, help="Path to a config json file")
    parser.add_argument("--state_dict", default=None, type=str, help="Optional path to saved block state dict")
    parser.add_argument("--layer_index", default=0, type=int, help="Optional path to saved block state dict")
    parser.add_argument("--num_steps", default=500, type=int, help="How many inference steps to run")
    parser.add_argument("--device", default=None, type=str, help="Run inference on this device")
    parser.add_argument("--block-path", default='', type=str, help="The path to the Bloom block-path")
    args = parser.parse_args()

    if args.device is None:
        args.device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f'Using device {args.device}')

    config = DistributedBloomConfig.from_json_file(args.config)
    block = BloomBlock(config, args.layer_index)

    if args.block_path != '':
        print(f'Loading block from {args.block_path}')
        block.load_state_dict( torch.load(args.block_path))
        #print(list(block_data.keys()))
        #block.load(args.block_path)

    block = block.to(args.device)
    block = block.to(torch.bfloat16)

    cache = None

    for i in trange(args.num_steps):
        dummy_input = torch.randn(1, 1, config.hidden_size, device=args.device).to(torch.bfloat16)
        alibi = build_alibi_tensor(i + 1, config.num_attention_heads).to(args.device)
        with torch.no_grad():
            outputs, cache = block.forward(dummy_input, alibi=alibi, use_cache=True, layer_past=cache)

    print_device_info(args.device)
