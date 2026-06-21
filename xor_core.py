import struct
import time
import hashlib
import argparse
import sys
from datetime import datetime

"""
XOR Cipher Core
===============
Demonstrates keyed XOR encoding of an input string with a 64-bit key.
The output encodes a hash of the input and a TTL timestamp, then XORs
the combined value against the key — illustrating how symmetric XOR
can produce fixed-width encoded strings.

Usage:
    python3 xor_core.py encode --input <STRING> --ttl <YYYY-MM-DD>
    python3 xor_core.py verify --output <HEX> --input <STRING>

"""

def _hash_input(input_string: str) -> int:
    """Returns the first 32 bits of the input string's hash as an integer."""
    # Take the first 8 hex chars (32 bits) of the input as the hash component
    return int(input_string[:8], 16)

def _xor_transform(data: int, key: int) -> int:
    """
    Core XOR operation — applies a 64-bit key to a 64-bit data block.
    XOR is its own inverse: xor_transform(xor_transform(x, k), k) == x,
    making it trivially reversible given the key (and insecure without one).
    """
    return data ^ key

def xor_encode(input_string: str, ttl_date: datetime, key: int) -> str:
    """
    Produces a 64-bit XOR-encoded hex string.
    Layout: high 32 bits = hash of input_string, low 32 bits = TTL timestamp.
    The combined 64-bit integer is XORed against `key`.
    """
    input_hash = _hash_input(input_string)
    ttl_timestamp = int(ttl_date.timestamp())

    # Pack: [input hash (32)] | [ttl timestamp (32)]
    raw = (input_hash << 32) | ttl_timestamp

    encoded = _xor_transform(raw, key)
    return f"{encoded:016X}"

def xor_validate(encoded: str, input_string: str, key: int) -> bool:
    """
    Reverses the XOR encoding and checks both the input hash and TTL.
    Returns True only if the input hash matches and the TTL has not elapsed.
    """
    try:
        encoded_int = int(encoded, 16)
    except ValueError:
        return False

    # Reverse XOR (identical operation)
    decoded = _xor_transform(encoded_int, key)

    # Unpack
    input_hash_stored = (decoded >> 32) & 0xFFFFFFFF
    ttl_timestamp_stored = decoded & 0xFFFFFFFF

    # Check input hash
    if input_hash_stored != _hash_input(input_string):
        return False

    # Check TTL
    if int(time.time()) > ttl_timestamp_stored:
        return False

    return True

def get_ttl_date(encoded: str, key: int) -> datetime:
    """Extracts the TTL date embedded in an encoded string."""
    decoded = _xor_transform(int(encoded, 16), key)
    ttl_timestamp = decoded & 0xFFFFFFFF
    return datetime.fromtimestamp(ttl_timestamp)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="XOR Cipher Core — CLI demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Encode:
    python3 xor_core.py encode --input <STRING> --ttl 2025-12-31

  Verify:
    python3 xor_core.py verify --output <HEX> --input <STRING>
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    enc_parser = subparsers.add_parser("encode", help="XOR-encode an input string with a TTL")
    enc_parser.add_argument("--input", required=True, help="Input string to encode")
    enc_parser.add_argument("--ttl", required=True, help="TTL date (YYYY-MM-DD)")
    enc_parser.add_argument("--key", type=lambda x: int(x, 16), default=0x1234567890ABCDEF, help="64-bit XOR key (hex)")

    ver_parser = subparsers.add_parser("verify", help="Verify an encoded output")
    ver_parser.add_argument("--output", required=True, help="Encoded hex string to verify")
    ver_parser.add_argument("--input", required=True, help="Original input string")
    ver_parser.add_argument("--key", type=lambda x: int(x, 16), default=0x1234567890ABCDEF, help="64-bit XOR key (hex)")

    args = parser.parse_args()

    if args.command == "encode":
        try:
            ttl = datetime.strptime(args.ttl, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            result = xor_encode(args.input, ttl, args.key)
            print(f"Encoded: {result}")
            print(f"TTL:     {ttl}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "verify":
        ok = xor_validate(args.output, args.input, args.key)
        if ok:
            ttl = get_ttl_date(args.output, args.key)
            print("Result: VALID")
            print(f"TTL:    {ttl}")
            sys.exit(0)
        else:
            print("Result: INVALID")
            sys.exit(1)

    else:
        parser.print_help()
