BASE_YAW = 0.60
BASE_PITCH = 0.28

YAW_LIMIT = 0.35        # how far sideways before "looking away"
PITCH_DOWN_LIMIT = 0.10  # pitch increase before "looking down"
PITCH_UP_LIMIT = 0.08    # pitch decrease before "looking up"


def classify(yaw, pitch):
    """Returns (status, is_attentive)."""
    if abs(yaw - BASE_YAW) > YAW_LIMIT:
        return "LOOKING AWAY", False
    if pitch - BASE_PITCH > PITCH_DOWN_LIMIT:
        return "LOOKING DOWN", False
    if BASE_PITCH - pitch > PITCH_UP_LIMIT:
        return "LOOKING UP", False
    return "ATTENTIVE", True