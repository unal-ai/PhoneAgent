import base64


def try_decode(s):
    try:
        base64.b64decode(s)
        print(f"'{s}': Decoded successfully")
    except Exception as e:
        print(f"'{s}': {e}")


try_decode(None)
try_decode("None")
try_decode("None ")
try_decode("data:image/png;base64,None")
try_decode("data:image/png;base64,")
try_decode("invalid_base64!")
try_decode(b"None")
