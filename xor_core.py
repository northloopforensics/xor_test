import argparse
import hashlib
import re
import sys
import time
from datetime import UTC, datetime

"""
XOR Cipher Core
===============
Demonstrates keyed XOR encoding of an input string with a 64-bit key.
The output encodes a hash of the input and a TTL timestamp, then XORs
the combined value against the key — illustrating how symmetric XOR
can produce fixed-width encoded strings.

Usage:
    python3 xor_core.py encode --input <HARDWARE_ID> --ttl <YYYY-MM-DD>
    python3 xor_core.py encode --input <HARDWARE_ID> --perpetual
    python3 xor_core.py verify --output <HEX> --input <HARDWARE_ID>

"""

LICENSE_SALT = "peeper"
MESSAGEBOARD_NAME = "NLC Messageboard"
MESSAGEBOARD_KEY = int.from_bytes(hashlib.sha256(MESSAGEBOARD_NAME.encode()).digest()[:8], "big")


def _hash_input(input_string: str, use_salt: bool = True) -> int:
    """Legacy Peeps hashes salt:input; unsalted presets use the hardware hash directly."""
    if use_salt:
        salted = f"{LICENSE_SALT}:{input_string}"
        digest = hashlib.sha256(salted.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)
    return int(input_string[:8], 16)


def _xor_transform(data: int, key: int) -> int:
    """
    Core XOR operation — applies a 64-bit key to a 64-bit data block.
    XOR is its own inverse: xor_transform(xor_transform(x, k), k) == x,
    making it trivially reversible given the key (and insecure without one).
    """
    return data ^ key


def xor_encode(
    input_string: str, ttl_date: datetime | None, key: int, use_salt: bool = True
) -> str:
    """
    Produces a 64-bit XOR-encoded hex string.
    Layout: high 32 bits = hash of input_string, low 32 bits = TTL timestamp.
    The combined 64-bit integer is XORed against `key`.
    """
    if not 0 <= key <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("XOR key must be an unsigned 64-bit integer.")
    input_hash = _hash_input(input_string, use_salt)
    ttl_timestamp = 0 if ttl_date is None else int(ttl_date.timestamp())
    if ttl_date is not None and not 1 <= ttl_timestamp <= 0xFFFFFFFF:
        raise ValueError("Expiration is outside the supported 32-bit timestamp range.")

    # Pack: [input hash (32)] | [ttl timestamp (32)]
    raw = (input_hash << 32) | ttl_timestamp

    encoded = _xor_transform(raw, key)
    return f"{encoded:016X}"


def xor_validate(encoded: str, input_string: str, key: int, use_salt: bool = True) -> bool:
    """
    Reverses the XOR encoding and checks both the input hash and TTL.
    Returns True only if the input hash matches and the TTL has not elapsed.
    """
    if not re.fullmatch(r"[0-9a-fA-F]{16}", encoded):
        return False
    if not 0 <= key <= 0xFFFFFFFFFFFFFFFF:
        return False
    try:
        encoded_int = int(encoded, 16)
        input_hash = _hash_input(input_string, use_salt)
    except ValueError:
        return False

    # Reverse XOR (identical operation)
    decoded = _xor_transform(encoded_int, key)

    # Unpack
    input_hash_stored = (decoded >> 32) & 0xFFFFFFFF
    ttl_timestamp_stored = decoded & 0xFFFFFFFF

    # Check input hash
    if input_hash_stored != input_hash:
        return False

    # Check TTL
    return ttl_timestamp_stored == 0 or time.time() < ttl_timestamp_stored


def get_ttl_date(encoded: str, key: int) -> datetime | None:
    """Extracts the TTL date embedded in an encoded string."""
    if not 0 <= key <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("XOR key must be an unsigned 64-bit integer.")
    if not re.fullmatch(r"[0-9a-fA-F]{16}", encoded):
        raise ValueError("Encoded key must contain exactly 16 hexadecimal characters.")
    decoded = _xor_transform(int(encoded, 16), key)
    ttl_timestamp = decoded & 0xFFFFFFFF
    return None if ttl_timestamp == 0 else datetime.fromtimestamp(ttl_timestamp, UTC)


def messageboard_encode(hardware_id: str, expiration: datetime | None) -> str:
    """Standalone issuer matching the application format; None means perpetual."""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", hardware_id):
        raise ValueError("Hardware ID must contain exactly 64 hexadecimal characters.")
    if expiration is not None and expiration.tzinfo is None:
        raise ValueError("Messageboard expiration must include a timezone.")
    return xor_encode(hardware_id, expiration, MESSAGEBOARD_KEY, use_salt=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NLC Messageboard license issuer — XOR CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Encode:
    python3 xor_core.py encode --input <STRING> --ttl 2025-12-31

  Verify:
    python3 xor_core.py verify --output <HEX> --input <STRING>
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    enc_parser = subparsers.add_parser("encode", help="XOR-encode an input string with a TTL")
    enc_parser.add_argument("--input", required=True, help="Input string to encode")
    duration = enc_parser.add_mutually_exclusive_group(required=True)
    duration.add_argument("--ttl", help="Last licensed UTC date (YYYY-MM-DD)")
    duration.add_argument("--perpetual", action="store_true", help="No expiration on this device")
    enc_parser.add_argument(
        "--key", type=lambda x: int(x, 16), default=MESSAGEBOARD_KEY, help="64-bit XOR key (hex)"
    )
    enc_parser.add_argument(
        "--salted", action="store_true", help="Legacy salted mode, not Messageboard"
    )

    ver_parser = subparsers.add_parser("verify", help="Verify an encoded output")
    ver_parser.add_argument("--output", required=True, help="Encoded hex string to verify")
    ver_parser.add_argument("--input", required=True, help="Original input string")
    ver_parser.add_argument(
        "--key", type=lambda x: int(x, 16), default=MESSAGEBOARD_KEY, help="64-bit XOR key (hex)"
    )
    ver_parser.add_argument(
        "--salted", action="store_true", help="Legacy salted mode, not Messageboard"
    )

    args = parser.parse_args()

    if args.command == "encode":
        try:
            ttl = None
            if not args.perpetual:
                ttl = datetime.strptime(args.ttl, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=UTC
                )
            if not args.salted and not re.fullmatch(r"[0-9a-fA-F]{64}", args.input):
                raise ValueError("Hardware ID must contain exactly 64 hexadecimal characters.")
            result = xor_encode(args.input, ttl, args.key, use_salt=args.salted)
            print(f"Encoded: {result}")
            print(f"TTL:     {ttl.isoformat() if ttl else 'Perpetual (this device)'}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "verify":
        ok = (
            args.salted or re.fullmatch(r"[0-9a-fA-F]{64}", args.input) is not None
        ) and xor_validate(args.output, args.input, args.key, use_salt=args.salted)
        if ok:
            ttl = get_ttl_date(args.output, args.key)
            print("Result: VALID")
            print(f"TTL:    {ttl.isoformat() if ttl else 'Perpetual (this device)'}")
            sys.exit(0)
        else:
            print("Result: INVALID")
            sys.exit(1)

    else:
        parser.print_help()
