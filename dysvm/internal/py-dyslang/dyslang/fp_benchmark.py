import math
import struct
import hashlib


def detect_fp_differences(iterations=100, details=True):
    """
    This function performs various floating-point operations and math functions
    that may exhibit differences across platforms due to underlying C library
    implementations or floating-point behavior. It packs the results into bytes using
    big-endian order for consistency, computes a SHA-256 hash of the concatenated data,
    and returns a dictionary with the total hash, intermediate values as hex strings
    of their packed bytes, and lossy repr strings of the float values to allow isolating
    differences more easily.

    Args:
        iterations (int): Number of iterations for transcendental function tests (default: 100)
        details (bool): If True, return full detailed results. If False, return only total_hash (default: True)

    For transcendental functions, the lists in 'values' and 'repr_values' correspond to
    i=1 to iterations, where x = i * math.pi / iterations. If hashes differ between systems, compare
    the repr_values lists element-wise to see which specific step (index +1) shows a
    numerical difference, and check hex values for bit-level differences.

    Run this on different systems, compare the total_hash; if different, compare sub-hashes,
    values, and repr_values to pinpoint differences.
    """

    def pack_hex(x):
        return struct.pack(">d", x).hex()

    sections = {}
    all_bytes = b""

    # Signed zero section
    signed_bytes = b""
    copysign_val = math.copysign(1.0, -0.0)
    signed_bytes += struct.pack(">d", copysign_val)
    neg_zero_val = -0.0
    signed_bytes += struct.pack(">d", neg_zero_val)
    pos_zero_val = 0.0
    signed_bytes += struct.pack(">d", pos_zero_val)
    signed_hash = hashlib.sha256(signed_bytes).hexdigest()
    signed_values = [
        pack_hex(copysign_val),
        pack_hex(neg_zero_val),
        pack_hex(pos_zero_val),
    ]
    signed_repr_values = [repr(copysign_val), repr(neg_zero_val), repr(pos_zero_val)]
    sections["signed_zero"] = {
        "hash": signed_hash,
        "values": signed_values,
        "repr_values": signed_repr_values,
    }
    all_bytes += signed_bytes

    # Loop summation section
    a = 0.0
    for i in range(1, iterations * 100 + 1):
        a += 1.0 / i**2
    loop_sum_bytes = b""
    loop_sum_bytes += struct.pack(">d", a)
    loop_sum_hash = hashlib.sha256(loop_sum_bytes).hexdigest()
    sections["loop_sum"] = {
        "hash": loop_sum_hash,
        "values": [pack_hex(a)],
        "repr_values": [repr(a)],
    }
    all_bytes += loop_sum_bytes

    # math.fsum section
    nums = [1.0 / i**2 for i in range(1, iterations * 100 + 1)]
    fsum_result = math.fsum(nums)
    fsum_bytes = b""
    fsum_bytes += struct.pack(">d", fsum_result)
    fsum_hash = hashlib.sha256(fsum_bytes).hexdigest()
    sections["fsum"] = {
        "hash": fsum_hash,
        "values": [pack_hex(fsum_result)],
        "repr_values": [repr(fsum_result)],
    }
    all_bytes += fsum_bytes

    # Transcendental functions sections
    trans = {}

    # Sin
    sin_bytes = b""
    sin_values = []
    sin_repr_values = []
    for i in range(1, iterations + 1):
        x = i * math.pi / iterations
        val = math.sin(x)
        sin_bytes += struct.pack(">d", val)
        sin_values.append(pack_hex(val))
        sin_repr_values.append(repr(val))
    sin_hash = hashlib.sha256(sin_bytes).hexdigest()
    trans["sin"] = {
        "hash": sin_hash,
        "values": sin_values,
        "repr_values": sin_repr_values,
    }
    all_bytes += sin_bytes

    # Cos
    cos_bytes = b""
    cos_values = []
    cos_repr_values = []
    for i in range(1, iterations + 1):
        x = i * math.pi / iterations
        val = math.cos(x)
        cos_bytes += struct.pack(">d", val)
        cos_values.append(pack_hex(val))
        cos_repr_values.append(repr(val))
    cos_hash = hashlib.sha256(cos_bytes).hexdigest()
    trans["cos"] = {
        "hash": cos_hash,
        "values": cos_values,
        "repr_values": cos_repr_values,
    }
    all_bytes += cos_bytes

    # Tan
    tan_bytes = b""
    tan_values = []
    tan_repr_values = []
    for i in range(1, iterations + 1):
        x = i * math.pi / iterations
        cos_x = math.cos(x)
        val = math.tan(x) if cos_x != 0 else 0.0
        tan_bytes += struct.pack(">d", val)
        tan_values.append(pack_hex(val))
        tan_repr_values.append(repr(val))
    tan_hash = hashlib.sha256(tan_bytes).hexdigest()
    trans["tan"] = {
        "hash": tan_hash,
        "values": tan_values,
        "repr_values": tan_repr_values,
    }
    all_bytes += tan_bytes

    # Exp
    exp_bytes = b""
    exp_values = []
    exp_repr_values = []
    for i in range(1, iterations + 1):
        x = i * math.pi / iterations
        val = math.exp(x)
        exp_bytes += struct.pack(">d", val)
        exp_values.append(pack_hex(val))
        exp_repr_values.append(repr(val))
    exp_hash = hashlib.sha256(exp_bytes).hexdigest()
    trans["exp"] = {
        "hash": exp_hash,
        "values": exp_values,
        "repr_values": exp_repr_values,
    }
    all_bytes += exp_bytes

    # Log
    log_bytes = b""
    log_values = []
    log_repr_values = []
    for i in range(1, iterations + 1):
        x = i * math.pi / iterations
        val = math.log(1 + x)
        log_bytes += struct.pack(">d", val)
        log_values.append(pack_hex(val))
        log_repr_values.append(repr(val))
    log_hash = hashlib.sha256(log_bytes).hexdigest()
    trans["log"] = {
        "hash": log_hash,
        "values": log_values,
        "repr_values": log_repr_values,
    }
    all_bytes += log_bytes

    # Fmod
    fmod_bytes = b""
    fmod_values = []
    fmod_repr_values = []
    for i in range(1, iterations + 1):
        x = i * math.pi / iterations
        val = math.fmod(x, math.pi / 4)
        fmod_bytes += struct.pack(">d", val)
        fmod_values.append(pack_hex(val))
        fmod_repr_values.append(repr(val))
    fmod_hash = hashlib.sha256(fmod_bytes).hexdigest()
    trans["fmod"] = {
        "hash": fmod_hash,
        "values": fmod_values,
        "repr_values": fmod_repr_values,
    }
    all_bytes += fmod_bytes

    sections["transcendental"] = trans

    # Total hash
    total_hash = hashlib.sha256(all_bytes).hexdigest()
    sections["total_hash"] = total_hash

    # Return only total_hash if details is False
    if not details:
        return {"total_hash": total_hash}
    
    return sections

