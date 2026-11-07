"""JSON.stringify-compatible output (no spaces; numbers formatted like JS Number#toString)."""
import json
import math
from decimal import Decimal


def js_number(x) -> str:
    if isinstance(x, bool):
        return 'true' if x else 'false'
    if isinstance(x, int):
        return str(x)
    if math.isnan(x) or math.isinf(x):
        return 'null'
    if x == 0:
        return '0'
    sign = '-' if x < 0 else ''
    t = Decimal(repr(abs(x))).as_tuple()
    digits = ''.join(map(str, t.digits)).rstrip('0') or '0'
    # n: decimal point position so value = 0.DIGITS * 10^n
    n = len(t.digits) + t.exponent
    k = len(digits)
    if k <= n <= 21:
        s = digits + '0' * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + '.' + digits[n:]
    elif -6 < n <= 0:
        s = '0.' + '0' * (-n) + digits
    else:
        e = n - 1
        es = ('+' if e >= 0 else '-') + str(abs(e))
        s = digits[0] + ('.' + digits[1:] if k > 1 else '') + 'e' + es
    return sign + s


def dumps(v) -> str:
    if isinstance(v, dict):
        return '{' + ','.join(json.dumps(k) + ':' + dumps(x) for k, x in v.items()) + '}'
    if isinstance(v, (list, tuple)):
        return '[' + ','.join(dumps(x) for x in v) + ']'
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if v is None:
        return 'null'
    return js_number(v)
