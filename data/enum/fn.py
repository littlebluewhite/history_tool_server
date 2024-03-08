from enum import Enum


class FnEnum(str, Enum):
    mean = "mean"
    max = "max"
    last = "last"
